#!/usr/bin/env python
#
# Copyright 2020, Juha Vierinen, Markus Floer
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
"""
 Ionosonde receiver. Receive signals based on a fixed program using
 GPS timing.
export PYTHONPATH="/usr/local/lib/python3/dist-packages/"
sudo sysctl -w net.core.rmem_max=500000000
sudo sysctl -w net.core.wmem_max=25000000
"""
import argparse
import numpy as np
import uhd
import time
import threading
import numpy as n
import matplotlib.pyplot as plt
import sweep
import iono_logger as l
import uhd_gps_lock as gl
import stuffr

def write_to_file(buf,fname,dec=10):
    obuf=stuffr.decimate(buf,dec=dec)
    obuf.tofile(fname)

def receive_waveform(u,t0_full,f0,recv_buffer,log=None,N=10000000,file_idx=0):
    t0_ts=uhd.libpyuhd.types.time_spec(np.uint64(t0_full),0.0)
    print("receive starts at %1.2f"%(t0_full))
    tune_req=uhd.libpyuhd.types.tune_request(f0)
    
    
    # wait for moment right before transmit
    print(time.time())
    u.set_rx_freq(tune_req)
    while t0_full-time.time() > 0.1:
        time.sleep(0.01)
    print(time.time())

    stream_args=uhd.usrp.libtypes.StreamArgs("fc32","sc16")
    
    rx_stream=u.get_rx_stream(stream_args)

    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
    stream_cmd.num_samps=N
    stream_cmd.stream_now=False
    stream_cmd.time_spec=uhd.types.TimeSpec(t0_full)
#    stream_cmd.time_spec = 
    rx_stream.issue_stream_cmd(stream_cmd)
    
    md=uhd.types.RXMetadata()

    num_rx_samps=rx_stream.recv(recv_buffer,md,timeout=20.0)
    if num_rx_samps != N:
        if log != None:
            log.log("Dropped packet %d read."%(num_rx_samps))

    write_thread=threading.Thread(target=write_to_file,args=(recv_buffer,"/dev/shm/raw-%d.bin"%(file_idx)))
    write_thread.start()    
#    recv_buffer.tofile()
    print("done %1.2f %d timespec %1.2f num_samps %d"%(time.time(),num_rx_samps,md.time_spec.get_real_secs(),num_rx_samps))

    
def main():
    """
    Start up everything and run main loop from here.
    """
    # setup a logger
    log=l.logger("rx-%d.log"%(time.time()))
    log.log("Starting receiver")
    
    # define an ionosonde program
#    s=sweep.sweep(freqs=sweep.freqs60,freq_dur=10.0)
    # fast sweep
    s=sweep.sweep(freqs=sweep.freqs30,freq_dur=2.0)

    log.log("Sweep freqs:")
    log.log(str(s.freqs))
    log.log("Sweep length %1.2f s Freq step %1.2f"%(s.sweep_len_s,s.freq_dur))

    # Configuring USRP
    sample_rate=1000000

    # number of samples per freq
    N=int(sample_rate*s.freq_dur)
    
    usrp = uhd.usrp.MultiUSRP("recv_buff_size=1000000")
    usrp.set_rx_rate(sample_rate)
    subdev_spec=uhd.usrp.SubdevSpec("A:A")
    usrp.set_rx_subdev_spec(subdev_spec)

    # Synchronizing clock
    gl.sync_clock(usrp,log)

    # figure out when to start the cycle. Assuming that we've been
    # doing this since 1970 with a fixed sweep length :)
    t0=np.uint64(np.floor(time.time()/(s.sweep_len_s))*s.sweep_len_s+s.sweep_len_s)
    print("starting next sweep at %1.2f"%(s.sweep_len_s))
    t0s=s.t0s()
    # double buffered
    recv_buffers = [np.empty(N,dtype=n.complex64),np.empty(N,dtype=n.complex64)]
    buf_idx=0
#    recv_buffer = np.empty(10000000,dtype=n.complex64)
    while True:
        # run the sweep program
        for i in range(s.n_freqs):
            f0=s.freq(i)
            t0i=t0s[i%s.n_freqs]
            step_t0=t0+t0i
            print(step_t0)
            receive_waveform(usrp,np.uint64(step_t0),f0,recv_buffer=recv_buffers[buf_idx],log=log,N=N-50000,file_idx=i)
            buf_idx=(buf_idx+1)%2
        gps_lock=gl.check_lock(usrp)
        if gps_lock == False:
            if log != None:
                log.log("Warning. No GPS lock. Exiting and restarting.")
                # forgot to add this :)
                exit(0)
            print("Warning. No GPS lock")

        t0+=np.uint64(s.sweep_len_s)

    
if __name__ == "__main__":
    main()
