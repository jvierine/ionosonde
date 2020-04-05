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
import iono_config

import os
import psutil


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
            

def write_to_file(recv_buffer,fname,log,dec=10):
    print("writing to file %s"%(fname))
    obuf=stuffr.decimate(recv_buffer,dec=dec)
    obuf.tofile(fname)

def receive_continuous(u,t0,t_now,s,log,sample_rate=1000000.0):

    fvec=[]
    t0s=[]    
    for i in range(s.n_freqs):
        f,t=s.pars(i)
        fvec.append(f)
        t0s.append(t)
    
    stream_args=uhd.usrp.StreamArgs("fc32","sc16")    
    rx_stream=u.get_rx_stream(stream_args)
    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
    stream_cmd.stream_now=False
    stream_cmd.time_spec=uhd.types.TimeSpec(t0)
    rx_stream.issue_stream_cmd(stream_cmd)
    md=uhd.types.RXMetadata()

    max_samps_per_packet = rx_stream.get_max_num_samps()
    
    recv_buffer=n.zeros(max_samps_per_packet,dtype=n.complex64)
    timeout=(t0-t_now)+5.0



    output_buffer = n.zeros(2*int(s.freq_dur*sample_rate),dtype=n.complex64)
    wr_buff = n.zeros(int(s.freq_dur*sample_rate),dtype=n.complex64)
    bl=len(output_buffer)
    bi=0
    
    fi = 0
    prev_samples = -1

    samples0=int(stream_cmd.time_spec.get_full_secs())*int(sample_rate) + int(stream_cmd.time_spec.get_frac_secs()*sample_rate)
    # number of samples per frequency
    n_per_freq=int(s.freq_dur*sample_rate)
    n_per_sweep=int(s.sweep_len_s*sample_rate)    

    sweep_num=0
    freq_num=0    
    next_sample = samples0 + n_per_freq
    cycle_t0 = t0
    while True:
        num_rx_samps=rx_stream.recv(recv_buffer,md,timeout=timeout)
        if num_rx_samps == 0:
            # shit happened. gotta try again
            log.log("dropped packet. number of received samples is 0")
            continue
        
        # the start of the buffer is at this sample index
        samples=int(md.time_spec.get_full_secs())*int(sample_rate) + int(md.time_spec.get_frac_secs()*sample_rate)

        # this is how many samples we have jumped forward.
        step = samples-prev_samples

        if prev_samples == -1:
            step = 363
            
        if step != 363 or num_rx_samps != 363:
            log.log("anomalous step %d num_rx_samps %d "%(step,num_rx_samps))
            
        prev_samples=samples

        # write the result into the output buffer
        output_buffer[ n.mod(bi+n.arange(num_rx_samps,dtype=n.uint64),bl) ]=recv_buffer

        bi=bi+step

        if samples > next_sample:
            idx0=bi-n_per_freq
            wr_buff[:]=output_buffer[n.mod(idx0+n.arange(n_per_freq,dtype=n.uint64),bl)]
            
            wr_thread=threading.Thread(target=write_to_file,args=(wr_buff,"%s/raw-%d-%03d.bin"%(iono_config.data_path,cycle_t0,freq_num),log))
            wr_thread.start()
            freq_num += 1
            # we cycle over
            if freq_num == s.n_freqs:
                cycle_t0 += s.sweep_len_s
                freq_num=0
                log.log("Starting new cycle")
            
            # we've got a full freq step
            next_sample += n_per_freq

        # timestamp of first sample
        t_head=md.time_spec.get_real_secs()

        t_sweep=n.mod(t_head-t0,s.sweep_len_s)
        n_sweep = int(n.floor(t_sweep/s.freq_dur))
        if n_sweep != fi:
            print("freq %d tuning to %1.2f MHz at %1.6f"%(n_sweep,fvec[n_sweep]/1e6,t_head))
            tune_req=uhd.libpyuhd.types.tune_request(fvec[n_sweep])
            u.set_rx_freq(tune_req)
            fi=n_sweep
        
        timeout=0.1


    
def main():
    """
    Start up everything and run main loop from here.
    """
    # setup a logger
    logfile="rx-%d.log"%(time.time())
    log=l.logger(logfile)
    log.log("Starting receiver")
    os.system("ln -s %s rx-current.log"%(logfile))
    
    s=iono_config.s
    log.log("Sweep freqs:")
    log.log(str(s.freqs))
    log.log("Sweep length %1.2f s Freq step %1.2f"%(s.sweep_len_s,s.freq_dur))

    # Configuring USRP
    sample_rate=iono_config.sample_rate

    # number of samples per freq
    N=int(sample_rate*s.freq_dur)

    # configure usrp
    usrp = uhd.usrp.MultiUSRP("recv_buff_size=500000000")
    usrp.set_rx_rate(sample_rate)
    subdev_spec=uhd.usrp.SubdevSpec(iono_config.rx_subdev)
    usrp.set_rx_subdev_spec(subdev_spec)

    # Synchronizing clock
    gl.sync_clock(usrp,log)

    # figure out when to start the cycle.
    t_now=usrp.get_time_now().get_real_secs()
    t0=np.uint64(np.floor(t_now/(s.sweep_len_s))*s.sweep_len_s+s.sweep_len_s)
    print("starting next sweep at %1.2f in %1.2f s, time now %1.2f"%(t0,t0-t_now,t_now))

    # start with initial frequency
    tune_req=uhd.libpyuhd.types.tune_request(s.freq(0))
    usrp.set_rx_freq(tune_req)
    
    
    # start reading data
    read_thread=threading.Thread(target=receive_continuous,args=(usrp,t0,t_now,s,log))
    read_thread.start()

    while True:
        t0=usrp.get_time_now().get_real_secs()
        delete_old_files(int(t0)-int(s.sweep_len_s)*3,iono_config.data_path)
        gl.check_lock(usrp,log,exit_if_not_locked=True)
        t0+=np.uint64(s.sweep_len_s)

        process = psutil.Process(os.getpid())
        log.log("Memory use %1.5f (MB)"%(process.memory_info().rss/1e6))

        time.sleep(s.sweep_len_s)


        

    
if __name__ == "__main__":
    main()
