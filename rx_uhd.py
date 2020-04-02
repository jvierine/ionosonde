#!/usr/bin/env python
#
# Copyright 2017-2018 Ettus Research, a National Instruments Company
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
"""
Receive signals in a synchronous manner with the transmitter
"""
import argparse
import numpy as np
import uhd
import time
import threading
import numpy as n
import matplotlib.pyplot as plt
import sweep

def sync_clock(u):
    # synchronize the usrp clock to the pc clock
    # assume that the pc clock is synchronized using ntp
    u.set_clock_source("gpsdo")
    u.set_time_source("gpsdo")
    t0=time.time()
    while (np.ceil(t0)-t0) < 0.2:
        t0=time.time()
        time.sleep(0.1)
        
    u.set_time_next_pps(uhd.libpyuhd.types.time_spec(np.ceil(t0)))
    t_now=time.time()
    t_usrp=(u.get_time_now().get_full_secs()+u.get_time_now().get_frac_secs())
    # these should be similar
    print("pc clock %1.2f usrp clock %1.2f"%(t_now,t_usrp))
    
def receive_waveform(u,t0_full,f0,N=10000000,file_idx=0):
    t0_ts=uhd.libpyuhd.types.time_spec(np.uint64(t0_full),0.0)
    print("receive starts at %1.2f"%(t0_full))
    tune_req=uhd.libpyuhd.types.tune_request(f0)
    # wait for moment right before transmit
    while t0_full-time.time() > 0.1:
        time.sleep(0.01)
    u.set_rx_freq(tune_req)

    stream_args=uhd.usrp.libtypes.StreamArgs("fc32","sc16")
    
    rx_stream=u.get_rx_stream(stream_args)

    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
    stream_cmd.num_samps=N
    stream_cmd.stream_now=False
    stream_cmd.time_spec=uhd.types.TimeSpec(t0_full)
#    stream_cmd.time_spec = 
    rx_stream.issue_stream_cmd(stream_cmd)
    recv_buffer = np.empty(N,dtype=n.complex64)
    md=uhd.types.RXMetadata()

    num_rx_samps=rx_stream.recv(recv_buffer,md,timeout=2.0)
    recv_buffer.tofile("/dev/shm/raw-%d.bin"%(file_idx))
    print("done %1.2f %d timespec %1.2f num_samps %d"%(time.time(),num_rx_samps,md.time_spec.get_real_secs(),num_rx_samps))

    
def main():
    """TX samples based on input arguments"""

    # define an ionosonde program
    s=sweep.sweep(freqs=sweep.freqs60,freq_dur=10.0)
    print(s.sweep_len_s)
    sample_rate=1000000
    usrp = uhd.usrp.MultiUSRP()
    usrp.set_rx_rate(sample_rate)
    subdev_spec=uhd.usrp.SubdevSpec("A:A")
    usrp.set_rx_subdev_spec(subdev_spec)
    sync_clock(usrp)

    # figure out when to start the cycle
    t0=np.uint64(np.floor(time.time()/(s.sweep_len_s))*s.sweep_len_s+s.sweep_len_s)
    print("starting next sweep at %1.2f"%(s.sweep_len_s))
    t0s=s.t0s()
    print(t0s)
    while True:
        for i in range(s.n_freqs):
            f0=s.freq(i)
            t0i=t0s[i%s.n_freqs]
            step_t0=t0+t0i
            print(step_t0)
            receive_waveform(usrp,np.uint64(step_t0),f0,N=9000000,file_idx=i)
        t0+=np.uint64(s.sweep_len_s)

    print("started tx thread")

    
if __name__ == "__main__":
    main()
