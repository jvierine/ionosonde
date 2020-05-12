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
import uhd
import time
import threading
import numpy as n
import matplotlib.pyplot as plt
import os

# internal modules related with the ionosonde
import sweep
import gps_lock as gl
import iono_logger as l
import iono_config

def tune_at(u,t0,f0=4e6,gpio_state=0):
    """ 
    tune radio to frequency f0 at t0_full 
    use a timed command.
    """
    u.clear_command_time()
    t0_ts=uhd.libpyuhd.types.time_spec(t0)
    print("tuning to %1.2f MHz at %1.2f"%(f0/1e6,t0_ts.get_real_secs()))
    u.set_command_time(t0_ts)
    tune_req=uhd.libpyuhd.types.tune_request(f0)
    u.set_tx_freq(tune_req)
    u.set_rx_freq(tune_req)
    
    if gpio_state == 0:
        out=0x00
    else:
        out=0x01
    gpio_line=0x01 # pin 0
    print("TX A GPIO pin 0=%d"%(out))
    u.set_gpio_attr("TXA","OUT",out,gpio_line,0)
    u.clear_command_time()

def tx_send(tx_stream,waveform,md,timeout=11.0):
    # this command will block until everything is in the transmit
    # buffer.
    tx_stream.send(waveform,md,timeout=(len(waveform)/float(iono_config.sample_rate))+1.0)

def rx_swr(u,t0,recv_buffer,f0,log):
    """
    Receive samples for a reflected power measurement
    USRP output connected to input with 35 dB attenuation gives 
    9.96 dB reflected power.
    """
    N=len(recv_buffer)
    stream_args=uhd.usrp.StreamArgs("fc32","sc16")    
    rx_stream=u.get_rx_stream(stream_args)
    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
    stream_cmd.num_samps=N
    stream_cmd.stream_now=False
    stream_cmd.time_spec=uhd.types.TimeSpec(t0)
    rx_stream.issue_stream_cmd(stream_cmd)    
    md=uhd.types.RXMetadata()
    num_rx_samps=rx_stream.recv(recv_buffer,md,timeout=float(N/iono_config.sample_rate)+1.0)
    pwr=n.mean(n.abs(recv_buffer)**2.0)
    rx_stream=None
    refl_pwr_dBm=10.0*n.log10(pwr)+iono_config.reflected_power_cal_dB
    log.log("reflected pwr %1.4f (MHz) %1.4f (dBm)"%(f0,refl_pwr_dBm))

def transmit_waveform(u,t0_full,waveform,swr_buffer,f0,log):
    """
    Transmit a timed burst 
    """
    t0_ts=uhd.libpyuhd.types.time_spec(n.uint64(t0_full),0.0)
    stream_args=uhd.usrp.StreamArgs("fc32","sc16")
    md=uhd.types.TXMetadata()
    md.has_time_spec=True
    md.time_spec=t0_ts
    
    print("transmit start at %1.2f"%(t0_full))
    
    # wait for moment right before transmit
    t_now=u.get_time_now().get_real_secs()
    print("setup time %1.2f"%(t_now))
    if t_now > t0_full:
        log.log("Delayed start for transmit %1.2f %1.2f"%(t_now,t0_full))
    if t0_full-t_now > 0.1:
        time.sleep(t0_full-t_now-0.1)

    try:
        # transmit the code
        tx_stream=u.get_tx_stream(stream_args)
        tx_thread = threading.Thread(target=tx_send,args=(tx_stream,waveform,md))
        tx_thread.daemon=True # exit if parent thread exits
        tx_thread.start()

        # do an swr measurement
        rx_thread = threading.Thread(target=rx_swr,args=(u,t0_full,swr_buffer,f0,log))
        rx_thread.daemon=True # exit if parent thread exits
        rx_thread.start()
        tx_thread.join()
        rx_thread.join()
        tx_stream=None
    except:
        exit(0)
    
def main():
    """
    The main loop for the ionosonde transmitter
    """
    t_start=time.time()
    logfname="tx-%d.log"%(t_start)
    log=l.logger(logfname)
    os.system("ln -sf %s tx-current.log"%(logfname))
    log.log("Starting TX sweep",print_msg=True)

    # this is the sweep configuration
    s=iono_config.s
    
    sample_rate=iono_config.sample_rate
    
    # use the address configured for the transmitter
    usrp = uhd.usrp.MultiUSRP("addr=%s"%(iono_config.tx_addr))
    usrp.set_tx_rate(sample_rate)
    usrp.set_rx_rate(sample_rate)
    
    rx_subdev_spec=uhd.usrp.SubdevSpec(iono_config.rx_subdev)
    tx_subdev_spec=uhd.usrp.SubdevSpec(iono_config.tx_subdev)
    
    usrp.set_tx_subdev_spec(tx_subdev_spec)
    usrp.set_rx_subdev_spec(rx_subdev_spec)

    # wait until GPS is locked, then align USRP time with global ref
    gl.sync_clock(usrp,log,min_sync_time=iono_config.min_gps_lock_time)
    
    # start with first frequency on tx and rx
    tune_req=uhd.libpyuhd.types.tune_request(s.freq(0))
    usrp.set_tx_freq(tune_req)
    usrp.set_rx_freq(tune_req)

    # hold SWR measurement about half of the transmit waveform length, so
    # we have no timing issues
    swr_buffer=n.empty(int(0.5*sample_rate*s.freq_dur),dtype=n.complex64)
     
    # figure out when to start the cycle
    t_now=usrp.get_time_now().get_real_secs()    
    t0=n.uint64(n.floor(t_now/(s.sweep_len_s))*s.sweep_len_s+s.sweep_len_s)
    print("starting next sweep at %1.2f"%(s.sweep_len_s))

    gpio_state=0
    while True:
        log.log("Starting sweep at %1.2f"%(t0))
        for i in range(s.n_freqs):
            f0,dt=s.pars(i)
            
            print("f=%f bandwidth %d kHz"%(f0,s.bw(i)*1e3))
            transmit_waveform(usrp,n.uint64(t0+dt),s.waveform(i),swr_buffer,f0,log)                
            
            # tune to next frequency 0.0 s before end
            next_freq_idx=(i+1)%s.n_freqs
            tune_at(usrp,t0+dt+s.freq_dur-0.05,f0=s.freq(next_freq_idx),gpio_state=gpio_state)
            gpio_state=(gpio_state+1)%2

            # check that GPS is still locked.
            gl.check_lock(usrp,log,exit_if_not_locked=True)

        t0+=n.uint64(s.sweep_len_s)

    
if __name__ == "__main__":
    main()
