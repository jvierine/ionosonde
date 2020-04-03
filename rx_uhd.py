#!/usr/bin/env python
#
# Copyright 2020, Juha Vierinen, Markus Floer
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
import iono_logger as l
import uhd_gps_lock as gl
import stuffr
import glob
import re
import os

#import cc_ram # analysis

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
            

def write_to_file(u,N,t0_full,recv_buffer,fname,log,dec=10):
    
    stream_args=uhd.usrp.libtypes.StreamArgs("fc32","sc16")    
    rx_stream=u.get_rx_stream(stream_args)
    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
    stream_cmd.num_samps=N
    stream_cmd.stream_now=False
    stream_cmd.time_spec=uhd.types.TimeSpec(t0_full)
    rx_stream.issue_stream_cmd(stream_cmd)
    md=uhd.types.RXMetadata()
    # this part could be improved by processing the stream one
    # packet at a time and padding zeros when a drop is
    # detected.
    num_rx_samps=rx_stream.recv(recv_buffer,md,timeout=20.0)
    if num_rx_samps != N:
        if log != None:
            log.log("Dropped packet %d read."%(num_rx_samps))
    
    obuf=stuffr.decimate(recv_buffer,dec=dec)
    obuf.tofile(fname)
    print("done %1.2f timespec %1.2f num_samps %d"%(time.time(),md.time_spec.get_real_secs(),num_rx_samps))

def receive_waveform(u,t0_full,f0,recv_buffer,log=None,N=10000000,file_idx=0,sweep_idx=0):
    t0_ts=uhd.libpyuhd.types.time_spec(np.uint64(t0_full),0.0)
        
    # wait for moment right before transmit
    while t0_full-time.time() > 0.05:
        time.sleep(0.01)
    tune_req=uhd.libpyuhd.types.tune_request(f0)
    u.set_rx_freq(tune_req)
    print("Launching receive at %1.2f now=%1.2f"%(t0_full,time.time()))
    
    #(u,N,t0_full,recv_buffer,fname,dec=10)
    # farming this out to a thread.
    write_thread=threading.Thread(target=write_to_file,args=(u,N,t0_full,recv_buffer,"/dev/shm/raw-%d-%03d.bin"%(sweep_idx,file_idx),log))
    write_thread.start()

    
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

    # configure usrp
    usrp = uhd.usrp.MultiUSRP("recv_buff_size=500000000")
    usrp.set_rx_rate(sample_rate)
    subdev_spec=uhd.usrp.SubdevSpec("A:A")
    usrp.set_rx_subdev_spec(subdev_spec)

    # Synchronizing clock
    gl.sync_clock(usrp,log)

    # figure out when to start the cycle. 
    t0=np.uint64(np.floor(time.time()/(s.sweep_len_s))*s.sweep_len_s+s.sweep_len_s)
    print("starting next sweep at %1.2f"%(s.sweep_len_s))
    
    # double buffer
    recv_buffers = [np.empty(N,dtype=n.complex64),np.empty(N,dtype=n.complex64)]
    buf_idx=0
    
    while True:
        del_thread=threading.Thread(target=delete_old_files,args=(int(t0)-int(s.sweep_len_s)*2,))
        del_thread.start()
        
        log.log("Starting sweep")
        
        # run the sweep program
        for i in range(s.n_freqs):
            f0,dt=s.pars(i)
            receive_waveform(usrp,np.uint64(t0+dt),f0,recv_buffer=recv_buffers[buf_idx],log=log,N=N-50000,file_idx=i,sweep_idx=t0)
            buf_idx=(buf_idx+1)%2
            
        gl.check_lock(usrp,log,exit_if_not_locked=True)
        t0+=np.uint64(s.sweep_len_s)

        

    
if __name__ == "__main__":
    main()
