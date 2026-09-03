#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Receive an ionosonde program from an existing DigitalRF wideband recording.

This is the ring-buffer counterpart of rx_uhd.py.  For each frequency dwell in
an ionosonde configuration it reads the corresponding UTC-aligned samples from
a wideband DigitalRF channel, shifts that RF frequency to zero, low-pass
filters and decimates it, and atomically publishes the same files consumed by
analyze_ionograms.py::

    raw-<sweep start Unix time>-<frequency index>.bin

The output files contain complex64 samples at config sample_rate / config dec.
"""

import argparse
import configparser
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import signal
import tempfile
import time

import numpy as np
from scipy.signal import firwin, upfirdn

try:
    import digital_rf as drf
except ImportError:  # Allow DSP unit tests on machines without DigitalRF.
    drf = None


STOP_AFTER_SWEEP = False


def request_stop(_signal_number, _frame):
    """Finish the current sweep after SIGUSR1, matching rx_uhd.py."""
    global STOP_AFTER_SWEEP
    STOP_AFTER_SWEEP = True


@dataclass(frozen=True)
class ReceiverProgram:
    frequencies_hz: tuple[float, ...]
    bandwidths_hz: tuple[float, ...]
    code_indices: tuple[int, ...]
    frequency_duration_s: float
    receiver_sample_rate_hz: int
    receiver_decimation: int
    output_dir: Path
    sweep_period_s: float

    @property
    def output_sample_rate_hz(self) -> int:
        if self.receiver_sample_rate_hz % self.receiver_decimation:
            raise ValueError("config sample_rate must be divisible by config dec")
        return self.receiver_sample_rate_hz // self.receiver_decimation

    @property
    def active_duration_s(self) -> float:
        return len(self.frequencies_hz) * self.frequency_duration_s


def load_program(path: str, output_dir: str | None = None) -> ReceiverProgram:
    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(path):
        raise FileNotFoundError(path)
    section = parser["config"]
    rows = json.loads(section["freqs"])
    code_indices = tuple(int(row[1]) for row in rows)
    bandwidths = tuple(float(value) for value in json.loads(section["bw"]))
    if not rows or not bandwidths:
        raise ValueError("configuration must contain frequencies and bandwidths")
    if min(code_indices) < 0 or max(code_indices) >= len(bandwidths):
        raise ValueError("frequency row refers to a nonexistent code/bandwidth")

    frequency_duration = float(json.loads(section["frequency_duration"]))
    if frequency_duration <= 0:
        raise ValueError("frequency_duration must be positive")
    active_duration = len(rows) * frequency_duration
    minute_multiple = math.ceil(active_duration / 60.0)
    sweeps_per_day = math.floor(24.0 * 60.0 / minute_multiple)
    sweep_period = 24.0 * 60.0 * 60.0 / sweeps_per_day

    configured_output = Path(json.loads(section["data_dir"])).expanduser()
    return ReceiverProgram(
        frequencies_hz=tuple(float(row[0]) * 1e6 for row in rows),
        bandwidths_hz=bandwidths,
        code_indices=code_indices,
        frequency_duration_s=frequency_duration,
        receiver_sample_rate_hz=int(json.loads(section["sample_rate"])),
        receiver_decimation=int(json.loads(section["dec"])),
        output_dir=Path(output_dir).expanduser() if output_dir else configured_output,
        sweep_period_s=sweep_period,
    )


def make_filter(input_rate_hz: int, output_rate_hz: int, bandwidth_hz: float) -> np.ndarray:
    """Return a symmetric FIR whose length supports exact chunk stitching."""
    if input_rate_hz % output_rate_hz:
        raise ValueError("input rate must be an integer multiple of output rate")
    decimation = input_rate_hz // output_rate_hz
    # Preserve as much of the configured full bandwidth as possible while
    # leaving an anti-alias transition before the output Nyquist frequency.
    cutoff_hz = min(0.5 * bandwidth_hz, 0.45 * output_rate_hz)
    if cutoff_hz <= 0:
        raise ValueError("passband must be positive")
    # L-1 is an integer multiple of D.  This makes the group-delay-compensated
    # sample position identical for every independently processed chunk.
    taps = firwin(8 * decimation + 1, cutoff_hz, fs=input_rate_hz, window=("kaiser", 8.0))
    return np.asarray(taps, dtype=np.float32)


def downconvert_block(
    reader,
    channel: str,
    input_rate_hz: int,
    input_center_hz: float,
    target_frequency_hz: float,
    dwell_start_sample: int,
    first_output_sample: int,
    output_count: int,
    decimation: int,
    taps: np.ndarray,
) -> np.ndarray:
    """Produce one group-delay-compensated output block from DigitalRF."""
    if (len(taps) - 1) % decimation:
        raise ValueError("filter length minus one must be divisible by decimation")
    half = (len(taps) - 1) // 2
    target_source_sample = dwell_start_sample + first_output_sample * decimation
    read_start = target_source_sample - half
    read_count = (output_count - 1) * decimation + len(taps)
    source = reader.read_vector_1d(read_start, read_count, channel)
    # Own the buffer because mixing is in-place; some reader/test backends may
    # return a view into reusable storage.
    source = np.array(source, dtype=np.complex64, copy=True)
    if source.size != read_count:
        raise RuntimeError(f"short DigitalRF read: expected {read_count}, got {source.size}")

    # Reference phase to the dwell start.  This avoids loss of precision from
    # multiplying RF offsets by a Unix timestamp while preserving phase across
    # independently processed chunks.
    relative_indices = np.arange(read_start - dwell_start_sample,
                                 read_start - dwell_start_sample + read_count,
                                 dtype=np.float64)
    offset_hz = target_frequency_hz - input_center_hz
    source *= np.exp(-2j * np.pi * offset_hz * relative_indices / input_rate_hz).astype(
        np.complex64
    )
    filtered = upfirdn(taps, source, down=decimation)
    delay_outputs = (len(taps) - 1) // decimation
    return np.asarray(filtered[delay_outputs : delay_outputs + output_count], dtype=np.complex64)


def wait_for_source(reader, channel: str, first_sample: int, last_sample: int,
                    poll_s: float) -> bool:
    """Wait for future data; return False if the requested start aged out."""
    while True:
        lower, upper = (int(value) for value in reader.get_bounds(channel))
        if first_sample < lower:
            return False
        if last_sample <= upper:
            return True
        time.sleep(poll_s)


def write_dwell(
    reader,
    channel: str,
    program: ReceiverProgram,
    input_rate_hz: int,
    input_center_hz: float,
    cycle_start_s: float,
    frequency_index: int,
    chunk_output_samples: int,
    poll_s: float,
) -> Path | None:
    output_rate = program.output_sample_rate_hz
    decimation = input_rate_hz // output_rate
    target_frequency = program.frequencies_hz[frequency_index]
    bandwidth = program.bandwidths_hz[program.code_indices[frequency_index]]
    taps = make_filter(input_rate_hz, output_rate, bandwidth)
    half = (len(taps) - 1) // 2

    source_low = input_center_hz - input_rate_hz / 2.0
    source_high = input_center_hz + input_rate_hz / 2.0
    passband_half_width = min(0.5 * bandwidth, 0.45 * output_rate)
    if target_frequency - passband_half_width < source_low or target_frequency + passband_half_width > source_high:
        aliased_frequency = (
            (target_frequency - input_center_hz + input_rate_hz / 2.0) % input_rate_hz
            - input_rate_hz / 2.0
            + input_center_hz
        )
        print(
            f"warning: {target_frequency / 1e6:g} MHz is outside nominal DigitalRF "
            f"coverage {source_low / 1e6:g}..{source_high / 1e6:g} MHz; "
            f"processing its complex-sampled alias at {aliased_frequency / 1e6:g} MHz",
            flush=True,
        )

    dwell_start_s = cycle_start_s + frequency_index * program.frequency_duration_s
    dwell_start_sample = int(round(dwell_start_s * input_rate_hz))
    output_count = int(round(program.frequency_duration_s * output_rate))
    required_first = dwell_start_sample - half
    required_last = dwell_start_sample + (output_count - 1) * decimation + half + 1
    if not wait_for_source(reader, channel, required_first, required_last, poll_s):
        print(f"source data aged out for sweep {int(cycle_start_s)}; skipping sweep", flush=True)
        return None

    program.output_dir.mkdir(parents=True, exist_ok=True)
    destination = program.output_dir / f"raw-{int(cycle_start_s)}-{frequency_index:03d}.bin"
    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}-", suffix=".tmp", dir=program.output_dir, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        try:
            for first in range(0, output_count, chunk_output_samples):
                count = min(chunk_output_samples, output_count - first)
                block = downconvert_block(
                    reader, channel, input_rate_hz, input_center_hz, target_frequency,
                    dwell_start_sample, first, count, decimation, taps,
                )
                block.tofile(temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    os.replace(temporary_path, destination)
    print(
        f"wrote {destination} ({output_count} complex64 samples, "
        f"{target_frequency / 1e6:g} MHz -> baseband)",
        flush=True,
    )
    return destination


def delete_old_outputs(program: ReceiverProgram, cycle_start_s: float, retention_sweeps: int) -> None:
    if retention_sweeps <= 0:
        return
    oldest_cycle = cycle_start_s - retention_sweeps * program.sweep_period_s
    for path in program.output_dir.glob("raw-*-*.bin"):
        try:
            cycle = int(path.name.split("-", 2)[1])
        except (IndexError, ValueError):
            continue
        if cycle < oldest_cycle:
            path.unlink()


def choose_cycle(reader, channel: str, program: ReceiverProgram,
                 input_rate_hz: int, once: bool) -> float:
    _lower, upper = reader.get_bounds(channel)
    available_end_s = int(upper) / input_rate_hz
    reference = available_end_s - program.active_duration_s if once else available_end_s
    return math.floor(reference / program.sweep_period_s) * program.sweep_period_s


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Receive an rx_uhd-compatible ionosonde sweep from a wideband DigitalRF ring buffer."
    )
    parser.add_argument("-c", "--config", default="config/default.ini")
    parser.add_argument("--input-dir", default="/dev/shm/hf25")
    parser.add_argument("--input-channel", default="ch0")
    parser.add_argument("--input-sample-rate", type=int, default=25_000_000)
    parser.add_argument("--input-center-frequency", type=float, default=12.5e6)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--chunk-output-samples", type=int, default=20_000)
    parser.add_argument("--poll-seconds", type=float, default=0.1)
    parser.add_argument("--retention-sweeps", type=int, default=3)
    parser.add_argument("--once", action="store_true", help="Process the newest complete sweep and exit.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if drf is None:
        raise RuntimeError("digital_rf is required to read the wideband ring buffer")
    if args.chunk_output_samples <= 0 or args.poll_seconds <= 0:
        raise ValueError("chunk-output-samples and poll-seconds must be positive")

    program = load_program(args.config, args.output_dir)
    output_rate = program.output_sample_rate_hz
    if args.input_sample_rate % output_rate:
        raise ValueError(
            f"input rate {args.input_sample_rate} is not divisible by output rate {output_rate}"
        )
    reader = drf.DigitalRFReader(args.input_dir)
    properties = reader.get_properties(args.input_channel)
    recorded_rate = int(round(float(properties["samples_per_second"])))
    if recorded_rate != args.input_sample_rate:
        raise ValueError(
            f"configured input rate {args.input_sample_rate} does not match "
            f"DigitalRF rate {recorded_rate}"
        )
    if args.verbose:
        print(
            f"DigitalRF {args.input_dir}/{args.input_channel}: {recorded_rate} samples/s; "
            f"output: {output_rate} samples/s in {program.output_dir}; "
            f"{len(program.frequencies_hz)} frequencies every {program.sweep_period_s:g} s",
            flush=True,
        )
    signal.signal(signal.SIGUSR1, request_stop)
    cycle_start = choose_cycle(
        reader, args.input_channel, program, args.input_sample_rate, args.once
    )

    while True:
        complete = True
        print(f"processing sweep {int(cycle_start)}", flush=True)
        for frequency_index in range(len(program.frequencies_hz)):
            result = write_dwell(
                reader, args.input_channel, program, args.input_sample_rate,
                args.input_center_frequency, cycle_start, frequency_index,
                args.chunk_output_samples, args.poll_seconds,
            )
            if result is None:
                complete = False
                break
        if complete:
            delete_old_outputs(program, cycle_start, args.retention_sweeps)
        if args.once or STOP_AFTER_SWEEP:
            break
        cycle_start += program.sweep_period_s
        now = time.time()
        if cycle_start + program.active_duration_s < now:
            cycle_start = math.floor(now / program.sweep_period_s) * program.sweep_period_s


if __name__ == "__main__":
    main()
