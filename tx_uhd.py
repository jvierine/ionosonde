#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
"""
Generate and TX samples using a set of waveforms, and waveform characteristics
"""

import argparse
import uhd
import time
import threading
import numpy as n
import matplotlib.pyplot as plt
import os
import signal

# internal modules related with the ionosonde
import sweep
import gps_lock as gl
import iono_logger
import iono_config
from datetime import datetime, timedelta


Exit = False        # Used to signal an orderly exit


def orderlyExit(signalNumber, frame):
    global Exit
    # Signal that we want to exit after current sweep
    Exit = True


def tune_at(u, t0, ic, f0=4e6, gpio_state=0):
    """
    tune radio to frequency f0 at t0_full
    use a timed command.

    Toggle watchdog pin 1/16 on TX DB
    Control antenna selector pin 2/16 on TX DB based on configuration
    """
    u.clear_command_time()
    t0_ts=uhd.libpyuhd.types.time_spec(t0)
    print("tuning to %1.2f MHz at %1.2f" % (f0/1e6, t0_ts.get_real_secs()))
    u.set_command_time(t0_ts)
    tune_req=uhd.libpyuhd.types.tune_request(f0)
    u.set_tx_freq(tune_req)
    u.set_rx_freq(tune_req)

    # toggle pin 1/16 for watchdog
    if gpio_state == 0:
        out=0x00
    else:
        out=0x01
    gpio_line=0xff
    # toggle pin 2/16 for antenna select
    if f0/1e6 > ic.antenna_select_freq:
        out= out | 0x02

    bits="{:02b}".format(out)
    print("Watchdog TX A GPIO=%s" % (bits))
    u.set_gpio_attr("TXA", "OUT", out, gpio_line, 0)

    u.clear_command_time()


def tx_send(tx_stream, waveform, md, ic, timeout=11.0):
    # this command will block until everything is in the transmit
    # buffer.
    tx_stream.send(waveform, md, timeout=(len(waveform)/float(ic.sample_rate))+1.0)


def rx_swr(u, t0, recv_buffer, f0, log, ic):
    """
    Receive samples for a reflected power measurement
    USRP output connected to input with 35 dB attenuation gives
    9.96 dB reflected power.
    """
    N=len(recv_buffer)
    stream_args=uhd.usrp.StreamArgs("fc32", "sc16")
    rx_stream=u.get_rx_stream(stream_args)
    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
    stream_cmd.num_samps=N
    stream_cmd.stream_now=False
    stream_cmd.time_spec=uhd.types.TimeSpec(t0)
    rx_stream.issue_stream_cmd(stream_cmd)
    md=uhd.types.RXMetadata()
    num_rx_samps=rx_stream.recv(recv_buffer, md, timeout=float(N/ic.sample_rate)+1.0)
    pwr=n.mean(n.abs(recv_buffer)**2.0)
    rx_stream=None
    if pwr <= 0.0:
        pwr=1e-99
    refl_pwr_dBm=10.0*n.log10(pwr)+ic.reflected_power_cal_dB
    log.log("reflected pwr %1.4f (MHz) %1.4f (dBm)" % (f0/1e6, refl_pwr_dBm))


def transmit_waveform(u, t0_full, waveform, swr_buffer, f0, log, ic):
    """
    Transmit a timed burst
    """
    t0_ts=uhd.libpyuhd.types.time_spec(n.uint64(t0_full), 0.0)
    stream_args=uhd.usrp.StreamArgs("fc32", "sc16")
    md=uhd.types.TXMetadata()
    md.has_time_spec=True
    md.time_spec=t0_ts

    t0_full_dt = datetime.fromtimestamp(t0_full)
    print("transmit start at %1.2f (%s)" % (t0_full, t0_full_dt.strftime("%FT%T.%f")[:-3]))

    # wait for moment right before transmit
    t_now=u.get_time_now().get_real_secs()
    t_now_dt = datetime.fromtimestamp(t_now)
    print("setup time %1.2f (%s)" % (t_now, t_now_dt.strftime("%FT%T.%f")[:-3]))
    if t_now > t0_full:
        log.log(
            "Delayed start for transmit %1.2f (%s)  %1.2f (%s)"
            % (
                t_now,
                t_now_dt.strftime("%FT%T.%f")[:-3],
                t0_full,
                t0_full_dt.strftime("%FT%T.%f")[:-3]
            )
        )
    if t0_full-t_now > 0.1:
        time.sleep(t0_full-t_now-0.1)

    try:
        # transmit the code
        tx_stream=u.get_tx_stream(stream_args)
        tx_thread = threading.Thread(target=tx_send, args=(tx_stream, waveform, md, ic))
        tx_thread.daemon=True  # exit if parent thread exits
        tx_thread.start()

        # do an swr measurement
        rx_thread = threading.Thread(target=rx_swr, args=(u, t0_full, swr_buffer, f0, log, ic))
        rx_thread.daemon=True  # exit if parent thread exits
        rx_thread.start()
        tx_thread.join()
        rx_thread.join()
        tx_stream=None
    except Exception as e:
        exit(0)


def main(config):
    """
    The main loop for the ionosonde transmitter
    """
    # setup a logger
    log = iono_logger.logger("tx-")

    # this is the sweep configuration
    s = ic.s

    # register signals to be caught
    signal.signal(signal.SIGUSR1, orderlyExit)

    sample_rate=ic.sample_rate

    # use the address configured for the transmitter
    usrp = uhd.usrp.MultiUSRP("addr=%s" % (ic.tx_addr))
    usrp.set_tx_rate(sample_rate)
    usrp.set_rx_rate(sample_rate)

    rx_subdev_spec=uhd.usrp.SubdevSpec(ic.rx_subdev)
    tx_subdev_spec=uhd.usrp.SubdevSpec(ic.tx_subdev)

    usrp.set_tx_subdev_spec(tx_subdev_spec)
    usrp.set_rx_subdev_spec(rx_subdev_spec)

    # wait until GPS is locked, then align USRP time with global ref
    gl.sync_clock(usrp, log, min_sync_time=ic.min_gps_lock_time)
    gps_mon=gl.gpsdo_monitor(usrp, log, ic.gps_holdover_time)

    # start with first frequency on tx and rx
    tune_req=uhd.libpyuhd.types.tune_request(s.freq(0))
    usrp.set_tx_freq(tune_req)
    usrp.set_rx_freq(tune_req)

    # hold SWR measurement about half of the transmit waveform length, so
    # we have no timing issues
    swr_buffer=n.empty(int(0.5*sample_rate*s.freq_dur), dtype=n.complex64)

    # figure out when to start the cycle
    t_now=usrp.get_time_now().get_real_secs()
    t0=n.uint64(n.floor(t_now/(s.sweep_len_s))*s.sweep_len_s+s.sweep_len_s)
    print("starting next sweep at %1.2f" % (s.sweep_len_s))

    gpio_state=0
    while not Exit:
        t0_dt = datetime.fromtimestamp(t0)
        log.log("Starting sweep at %1.2f (%s)" % (t0, t0_dt.strftime("%FT%T.%f")[:-3]))
        for i in range(s.n_freqs):
            f0, dt=s.pars(i)

            print("f=%f code %s" % (f0/1e6, s.code(i)))
            transmit_waveform(usrp, n.uint64(t0+dt), s.waveform(i), swr_buffer, f0, log, ic)

            # tune to next frequency 0.0 s before end
            next_freq_idx=(i+1) % s.n_freqs
            tune_at(usrp, t0+dt+s.freq_dur-0.05, ic, f0=s.freq(next_freq_idx), gpio_state=gpio_state)
            gpio_state=(gpio_state+1) % 2

            # check that GPS is still locked.
            gps_mon.check()

        t0+=n.uint64(s.sweep_len_s)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config',
        default="config/default.ini",
        help='''Configuration file. (default: %(default)s)''',
    )
    parser.add_argument(
        '-v', '--verbose',
        action="store_true",
        help='''Increase output verbosity. (default: %(default)s)''',
    )
    op = parser.parse_args()

    ic = iono_config.get_config(
        config=op.config,
        write_waveforms=True,
        quiet=not op.verbose
    )
    main(ic)
