#!/usr/bin/env python3
#
# Copyright 2020, Juha Vierinen, Markus Floer
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
"""
Generate and TX samples using a set of waveforms, and waveform characteristics
"""

import argparse
import numpy as np
import uhd
import time
import threading
import numpy as n
import matplotlib.pyplot as plt
#frequencies = np.arange(10.0)*100e3 + 3.5e6
#import freqs
import sweep
import uhd_gps_lock as gl
import iono_logger as l

def tune_at(u,t0,f0=4e6):
    """ 
    tune radio to frequency f0 at t0_full 
    """
    u.clear_command_time()
    t0_ts=uhd.libpyuhd.types.time_spec(t0)
    print("tuning at %1.2f"%(t0_ts.get_real_secs()))
    u.set_command_time(t0_ts)
    tune_req=uhd.libpyuhd.types.tune_request(f0)
    u.set_tx_freq(tune_req)
    u.set_rx_freq(tune_req)
    u.clear_command_time()

def tx_send(tx_stream,waveform,md,timeout=11.0):
    # this command will block until everything is in the transmit
    # buffer.
    tx_stream.send(waveform,md,timeout=11.0)

def rx_swr(u,t0,f0,recv_buffer):
    """
    Receive samples for a SWR measurement
    """
    N=len(recv_buffer)
    tune_req=uhd.libpyuhd.types.tune_request(f0)
    stream_args=uhd.usrp.libtypes.StreamArgs("fc32","sc16")    
    rx_stream=u.get_rx_stream(stream_args)
    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
    stream_cmd.num_samps=N
    stream_cmd.stream_now=False
    stream_cmd.time_spec=uhd.types.TimeSpec(t0)
    rx_stream.issue_stream_cmd(stream_cmd)    
    md=uhd.types.RXMetadata()
    num_rx_samps=rx_stream.recv(recv_buffer,md,timeout=20.0)
    pwr=n.sum(n.abs(recv_buffer)**2.0)
    print("Reflected pwr=%1.2f (dB)"%(10.0*n.log10(pwr)))

def transmit_waveform(u,t0_full,f0,waveform,swr_buffer):
    t0_ts=uhd.libpyuhd.types.time_spec(np.uint64(t0_full),0.0)
    stream_args=uhd.usrp.libtypes.StreamArgs("fc32","sc16")
    md=uhd.types.TXMetadata()
    md.has_time_spec=True
    md.time_spec=t0_ts
    print("transmit start at %1.2f"%(t0_full))
    # wait for moment right before transmit
    while t0_full-time.time() > 0.1:
        time.sleep(0.01)
        
    print("thread setup %1.3f"%(time.time()))
    tx_stream=u.get_tx_stream(stream_args)
    tx_thread = threading.Thread(target=tx_send,args=(tx_stream,waveform,md))
    tx_thread.start()
    
    rx_thread = threading.Thread(target=rx_swr,args=(u,t0_full,f0,swr_buffer))
    rx_thread.start()
    print("thread setup done %1.3f"%(time.time()))
    
def main():
    """TX samples based on input arguments"""
    log=l.logger("tx-%d.log"%(time.time()))
    log.log("Starting TX sweep",print_msg=True)
    
    # define an ionosonde program
    #s=sweep.sweep(freqs=sweep.freqs60,freq_dur=10.0)

    s=sweep.sweep(freqs=sweep.freqs30,freq_dur=2.0)
    
    sample_rate=1000000
    usrp = uhd.usrp.MultiUSRP()
    usrp.set_tx_rate(sample_rate)
    usrp.set_rx_rate(sample_rate)
    
    subdev_spec=uhd.usrp.SubdevSpec("A:A")
    usrp.set_tx_subdev_spec(subdev_spec)
    usrp.set_rx_subdev_spec(subdev_spec)

    # wait until GPS is locked, then align USRP time with global
    # reference
    gl.sync_clock(usrp,log)
    
    # start with first frequency
    tune_req=uhd.libpyuhd.types.tune_request(s.freq(0))
    usrp.set_tx_freq(tune_req)
    usrp.set_rx_freq(tune_req)
    
    code = np.fromfile("waveforms/code-l10000-b10-000000f.bin",dtype=np.complex64)
    n_reps=s.freq_dur*sample_rate/len(code)
    data=np.tile(code,int(n_reps))

    # hold SWR measurement
    swr_buffer=np.empty(int(len(data)*0.5),dtype=n.complex64)    
     
    # figure out when to start the cycle
    t0=np.uint64(np.floor(time.time()/(s.sweep_len_s))*s.sweep_len_s+s.sweep_len_s)
    print("starting next sweep at %1.2f"%(s.sweep_len_s))
    t0s=s.t0s()
    print(t0s)
    while True:
        for i in range(s.n_freqs):
            f0,dt=s.pars(i)
            
            transmit_waveform(usrp,np.uint64(t0+dt),f0,data,swr_buffer)
            
            # tune to next frequency 0.1 s before end
            tune_at(usrp,t0+dt+s.freq_dur-0.1,f0=s.freq(i+1))
            time.sleep(0.2)
            
            locked=gl.check_lock(usrp,log,exit_if_not_locked=True)

        t0+=np.uint64(s.sweep_len_s)

    print("started tx thread")

    
if __name__ == "__main__":
    main()
