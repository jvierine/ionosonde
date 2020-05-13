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
import gps_lock as gl
import stuffr
import glob
import re
import os
import iono_config
import scipy.signal
import os
import psutil

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
            

def write_to_file(recv_buffer,fname,log,dec=10,fl=20):
    print("writing to file %s"%(fname))

    # filter and decimate with Blackmann-Harris window
    w = n.zeros(fl, dtype=n.complex64)
    w[0:fl] = scipy.signal.blackmanharris(fl)
    # filter, time shift, decimate, and cast to complex64 data type
    obuf=n.array(n.roll(n.fft.ifft(n.fft.fft(w,len(recv_buffer))*n.fft.fft(recv_buffer)),-int(fl/2))[0:len(recv_buffer):dec],dtype=n.complex64)

    # rectangular impulse response. better for range resolution,
    # but not very good for frequency selectivity.
#    obuf=stuffr.decimate(recv_buffer,dec=dec)
    obuf.tofile(fname)

def receive_continuous(u,t0,t_now,s,log,sample_rate=1000000.0):
    """
    New receive script, which processes data incoming from the usrp
    one packet at a time.
    """

    # sweep timing and frequencies
    fvec=[]
    t0s=[]    
    for i in range(s.n_freqs):
        f,t=s.pars(i)
        fvec.append(f)
        t0s.append(t)

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

    tune_at(u,t0+s.freq_dur,f0=s.freq(1))

    locked=True
    try:
        while locked:
            num_rx_samps=rx_stream.recv(recv_buffer,md,timeout=timeout)
            if num_rx_samps == 0:
                # shit happened. we probably lost a packet. gotta try again
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
                wr_thread=threading.Thread(target=write_to_file,args=(wr_buff,"%s/raw-%d-%03d.bin"%(iono_config.data_path,cycle_t0,freq_num),log))
                wr_thread.start()
                freq_num += 1
    
                # setup tuning for next frequency
                tune_at(u,cycle_t0 + (freq_num+1)*s.freq_dur,f0=s.freq(freq_num+1))
                print("Tuning to %1.2f at %1.2f"%(s.freq(freq_num+1)/1e6,cycle_t0 + (freq_num+1)*s.freq_dur))
                
                # the cycle is over
                if freq_num == s.n_freqs:
                    cycle_t0 += s.sweep_len_s
                    freq_num=0
                    sweep_num+=1
                    locked=gl.check_lock(u,log,exit_if_not_locked=False)
                    log.log("Starting new cycle at %1.2f"%(cycle_t0))
            
                # we've got a full freq step
                next_sample += n_per_freq
            
            timeout=0.1
    except:
        print("interrupt")
        pass
    print("Issuing stop command...")
    
    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont)
    rx_stream.issue_stream_cmd(stream_cmd)
    time.sleep(1)
    print("Stream stopped")
    exit(0)
    return

def housekeeping(usrp,log,s):
    try:
        while True:
            t0=usrp.get_time_now().get_real_secs()
            delete_old_files(int(t0)-int(s.sweep_len_s)*3,iono_config.data_path)
            t0+=np.uint64(s.sweep_len_s)
            
            process = psutil.Process(os.getpid())
            log.log("Memory use %1.5f (MB)"%(process.memory_info().rss/1e6))
            
            time.sleep(s.sweep_len_s)
    except:
        print("Housekeeping thread stopped")
        pass
        
def main():
    """
    Start up everything and run main loop from here.
    """
    # setup a logger
    logfile="rx-%d.log"%(time.time())
    log=l.logger(logfile)
    log.log("Starting receiver")
    os.system("rm rx-current.log;ln -s %s rx-current.log"%(logfile))
    
    s=iono_config.s
    log.log("Sweep freqs:")
    log.log(str(s.freqs))
    log.log("Sweep length %1.2f s Freq step %1.2f"%(s.sweep_len_s,s.freq_dur))

    # Configuring USRP
    sample_rate=iono_config.sample_rate

    # number of samples per freq
    N=int(sample_rate*s.freq_dur)

    # configure usrp
    usrp = uhd.usrp.MultiUSRP("addr=%s,recv_buff_size=500000000"%(iono_config.rx_addr))
    usrp.set_rx_rate(sample_rate)
    subdev_spec=uhd.usrp.SubdevSpec(iono_config.rx_subdev)
    usrp.set_rx_subdev_spec(subdev_spec)

    # Synchronizing clock
    gl.sync_clock(usrp,log,min_sync_time=iono_config.min_gps_lock_time)

    # figure out when to start the cycle.
    t_now=usrp.get_time_now().get_real_secs()
    t0=np.uint64(np.floor(t_now/(s.sweep_len_s))*s.sweep_len_s+s.sweep_len_s)
    print("starting next sweep at %1.2f in %1.2f s, time now %1.2f"%(t0,t0-t_now,t_now))

    # start with initial frequency
    tune_req=uhd.libpyuhd.types.tune_request(s.freq(0))
    usrp.set_rx_freq(tune_req)
    
    
    # start reading data
    housekeeping_thread=threading.Thread(target=housekeeping,args=(usrp,log,s))
    housekeeping_thread.daemon=True
    housekeeping_thread.start()

    # infinitely loop on receive
    receive_continuous(usrp,t0,t_now,s,log)
    
if __name__ == "__main__":
    main()
