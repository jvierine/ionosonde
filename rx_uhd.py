#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
"""
 Ionosonde receiver. Receive signals based on a fixed program using
 GPS timing.
"""
import argparse
import numpy as np
import uhd
import time
import threading
import numpy as n
import matplotlib.pyplot as plt
import sweep
import iono_logger
import gps_lock as gl
import stuffr
import glob
import re
import os
import iono_config
import scipy.signal
import scipy.signal as ss
import os
import psutil
import signal
from datetime import datetime, timedelta
import traceback

Exit = False        # Used to signal an orderly exit


def orderlyExit(signalNumber, frame):
    global Exit
    # Signal that we want to exit after current sweep
    Exit = True


def tune_at(u,t0,f0=4e6):
    """
    tune radio to frequency f0 at t0_full
    use a timed command.
    """
    u.clear_command_time()
    t0_ts=uhd.libpyuhd.types.time_spec(t0)
    print("tuning at %1.2f"%(t0_ts.get_real_secs()))
    u.set_command_time(t0_ts)
    tune_req=uhd.libpyuhd.types.tune_request(f0)
    u.set_tx_freq(tune_req)
    u.set_rx_freq(tune_req)
    u.clear_command_time()

def delete_old_files(t0,data_path="/dev/shm"):
    """
    Deleting files older than two cycles ago
    """
    # delete older files
    fl=glob.glob("%s/raw*.bin"%(data_path))
    fl.sort()
    for f in fl:
        try:
            tfile=int(re.search(".*/raw-(.*)-....bin",f).group(1))
            if tfile < t0:
                os.system("rm %s"%(f))
        except:
            print("Error deleting file %s"%(f))

def lpf(dec=10,filter_len=4):
    """ a better lpf """
    om0=2.0*n.pi/dec
    dec2=filter_len*dec
    m=n.array(n.arange(filter_len*dec),dtype=n.float32)
    m=m-n.mean(m)
    # windowed low pass filter
    wfun=n.array(ss.hann(len(m))*n.sin(om0*(m+1e-6))/(n.pi*(m+1e-6)),dtype=n.complex64)
    return(wfun)

def write_to_file(recv_buffer,fname,log,dec=10):
    print("writing to file %s"%(fname))

    #    w=lpf(dec=dec)
    # todo: read filter length from create_waveforms, where it is determined
    w=ss.flattop(52)
    fl=len(w)
    # filter, time shift, decimate, and cast to complex64 data type
    obuf=n.array(n.roll(n.fft.ifft(n.fft.fft(w,len(recv_buffer))*n.fft.fft(recv_buffer)),-int(fl/2))[0:len(recv_buffer):dec],dtype=n.complex64)

    # rectangular impulse response. better for range resolution,
    # but not very good for frequency selectivity.
#    obuf=stuffr.decimate(recv_buffer,dec=dec)
    obuf.tofile(fname)

def receive_continuous(u,t0,t_now,ic,log,sample_rate=1000000.0):
    """
    New receive script, which processes data incoming from the usrp
    one packet at a time.
    """
    s=ic.s
    gps_mon=gl.gpsdo_monitor(u,log,exit_on_lost_lock=False)
    # sweep timing and frequencies
    fvec=[]
    t0s=[]
    for i in range(s.n_freqs):
        f,t=s.pars(i)
        fvec.append(f)
        t0s.append(t)
        
    # it seems that waiting until a few seconds before the sweep start
    # helps to keep the ethernet link "alive" for the start of streaming
    t_now=u.get_time_now().get_real_secs()
    while t0-t_now > 5.0:
        t_now=u.get_time_now().get_real_secs()
        print("Waiting for setup %1.2f"%(t0-t_now))
        time.sleep(1)
    t_now=u.get_time_now().get_real_secs()        
        
    # setup usrp to stream continuously, starting at t0
    stream_args=uhd.usrp.StreamArgs("fc32","sc16")
    rx_stream=u.get_rx_stream(stream_args)
    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
    stream_cmd.stream_now=False
    stream_cmd.time_spec=uhd.types.TimeSpec(t0)
    rx_stream.issue_stream_cmd(stream_cmd)
    md=uhd.types.RXMetadata()

    # this is how many samples we expect to get from each packet
    max_samps_per_packet = rx_stream.get_max_num_samps()

    # receive buffer size large enough to fit one packet
    recv_buffer=n.zeros(max_samps_per_packet,dtype=n.complex64)

    # initial timeout is long enough for us to receive the first packet, which
    # happens at t0
    timeout=(t0-t_now)+5.0

    # store data in this ringbuffer, and offload it to ram disk once
    # one full cycle is finished
    output_buffer = n.zeros(2*int(s.freq_dur*sample_rate),dtype=n.complex64)

    # use this buffer to write to a file
    wr_buff = n.zeros(int(s.freq_dur*sample_rate),dtype=n.complex64)
    bl=len(output_buffer)
    bi=0

    # frequency index
    fi = 0
    # samples since 1970 for the previous packet (no previous packet at first)
    prev_samples = -1

    # samples since 1970 for the first packet.
    samples0=int(stream_cmd.time_spec.get_full_secs())*int(sample_rate) + int(stream_cmd.time_spec.get_frac_secs()*sample_rate)

    # number of samples per frequency in the sweep
    n_per_freq=int(s.freq_dur*sample_rate)
    n_per_sweep=int(s.sweep_len_s*sample_rate)

    sweep_num=0
    freq_num=0
    next_sample = samples0 + n_per_freq
    cycle_t0 = t0

    # setup tuning for next frequency
    tune_at(u,t0+s.freq_dur,f0=s.freq(1))

    locked=True
    try:
        while locked and not Exit:
            num_rx_samps=rx_stream.recv(recv_buffer,md,timeout=timeout)
            if num_rx_samps == 0:
                # shit happened. we probably lost a packet. 
                log.log("dropped packet. number of received samples is 0")
                continue

            # the start of the buffer is at this sample index
            samples=int(md.time_spec.get_full_secs())*int(sample_rate) + int(md.time_spec.get_frac_secs()*sample_rate)

            # this is how many samples we have jumped forward.
            step = samples-prev_samples

            if prev_samples == -1:
                step = num_rx_samps

            if step != 363 or num_rx_samps != 363:
                log.log("anomalous step %d num_rx_samps %d "%(step,num_rx_samps))

            prev_samples=samples

            # write the result into the output buffer
            output_buffer[ n.mod(bi+n.arange(num_rx_samps,dtype=n.uint64),bl) ]=recv_buffer

            bi=bi+step

            if samples > next_sample:
                # this should be correct now.
                idx0=sweep_num*n_per_sweep+freq_num*n_per_freq

                wr_buff[:]=output_buffer[n.mod(idx0+n.arange(n_per_freq,dtype=n.uint64),bl)]

                # spin of a thread to write all samples obtained while sounding this frequency
                # todo: pass decimtaiton option, and pass transmit bandwidth
                wr_thread=threading.Thread(target=write_to_file,args=(wr_buff,"%s/raw-%d-%03d.bin"%(ic.data_dir,cycle_t0,freq_num),log))
                wr_thread.start()
                freq_num += 1

                # setup tuning for next frequency
                tune_time = cycle_t0 + (freq_num + 1) * s.freq_dur
                tune_time_dt = datetime.fromtimestamp(tune_time)
                tune_at(u, tune_time, f0=s.freq(freq_num + 1))
                print(
                    "Tuning to %1.2f at %1.2f (%s)"
                    % (
                        s.freq(freq_num + 1) / 1e6,
                        tune_time,
                        tune_time_dt.strftime("%FT%T.%f")[:-3]
                    )
                )

                # the cycle is over
                if freq_num == s.n_freqs:
                    cycle_t0 += s.sweep_len_s
                    freq_num=0
                    sweep_num+=1

                    locked=gps_mon.check()
                    log.log(
                        "Starting new cycle at %1.2f (%s)"
                        % (
                            cycle_t0,
                            datetime.fromtimestamp(cycle_t0).strftime("%FT%T.%f")[:-3]
                        )
                    )

                # we've got a full freq step
                next_sample += n_per_freq

            timeout=0.1
    except:
        traceback.print_exc()
        traceback.print_stack()
        print("interrupt")
        pass
    print("Issuing stop command...")
    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont)
    rx_stream.issue_stream_cmd(stream_cmd)

    num_rx_samps=rx_stream.recv(recv_buffer,md,timeout=0.1)
    while(num_rx_samps != 0):
        print("Clearing buffer")
        num_rx_samps=rx_stream.recv(recv_buffer,md,timeout=0.1)
    print("Stream stopped")
    exit(0)
    return

def housekeeping(usrp,log,ic):
    """
    Delete raw voltage files in ringbuffer
    """
    try:
        while True:
            t0=usrp.get_time_now().get_real_secs()
            delete_old_files(int(t0)-int(ic.s.sweep_len_s)*3,ic.data_dir)
            t0+=np.uint64(ic.s.sweep_len_s)

            process = psutil.Process(os.getpid())
            log.log("Memory use %1.5f (MB)"%(process.memory_info().rss/1e6))

            time.sleep(ic.s.sweep_len_s)
    except:
        print("Housekeeping thread stopped")
        pass


def main(ic):
    """
    Start up everything and run main loop from here.
    """
    # setup a logger
    log = iono_logger.logger("rx-")

    s = ic.s

    # register signals to be caught
    signal.signal(signal.SIGUSR1, orderlyExit)

    log.log("Sweep freqs:")
    log.log(str(s.freqs))
    log.log("Sweep length %1.2f s Freq step %1.2f"%(s.sweep_len_s,s.freq_dur))

    # Configuring USRP
    sample_rate=ic.sample_rate

    # number of samples per freq
    N=int(sample_rate*s.freq_dur)

    # configure usrp
    usrp = uhd.usrp.MultiUSRP("addr=%s,recv_buff_size=500000000"%(ic.rx_addr))
    usrp.set_rx_rate(sample_rate)
    subdev_spec=uhd.usrp.SubdevSpec(ic.rx_subdev)
    usrp.set_rx_subdev_spec(subdev_spec)

    # Synchronizing clock
    gl.sync_clock(usrp,log,min_sync_time=ic.min_gps_lock_time)

    # figure out when to start the cycle.
    t_now=usrp.get_time_now().get_real_secs()
    t_now_dt = datetime.fromtimestamp(t_now)
    # add 5 secs for setup time
    t0=np.uint64(np.floor((t_now+5.0)/(s.sweep_len_s))*s.sweep_len_s+s.sweep_len_s)
    t0_dt = datetime.fromtimestamp(t0)
    print(
        "starting next sweep at %1.2f (%s) in %1.2f s, time now %1.2f (%s)"
        % (
            t0,
            t0_dt.strftime("%FT%T.%f")[:-3],
            t0-t_now,
            t_now,
            t_now_dt.strftime("%FT%T.%f")[:-3]
        )
    )

    # start with initial frequency
    tune_req=uhd.libpyuhd.types.tune_request(s.freq(0))
    usrp.set_rx_freq(tune_req)


    # start reading data
    housekeeping_thread=threading.Thread(target=housekeeping,args=(usrp,log,ic))
    housekeeping_thread.daemon=True
    housekeeping_thread.start()

    # infinitely loop on receive
    receive_continuous(usrp,t0,t_now,ic,log)


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
