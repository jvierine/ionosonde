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

# internal modules related with the ionosonde
import sweep
import uhd_gps_lock as gl
import iono_logger as l
import iono_config

def tune_at(u,t0,f0=4e6):
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
    u.clear_command_time()

def tx_send(tx_stream,waveform,md,timeout=11.0):
    # this command will block until everything is in the transmit
    # buffer.
    tx_stream.send(waveform,md,timeout=(len(waveform)/float(iono_config.sample_rate))+1.0)

def rx_swr(u,t0,recv_buffer):
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
    pwr=n.sum(n.abs(recv_buffer)**2.0)
    rx_stream=None
    print("reflected pwr=%1.2f (dB)"%(10.0*n.log10(pwr)))

def transmit_waveform(u,t0_full,waveform,swr_buffer):
    """
    Transmit a timed burst 
    """
    t0_ts=uhd.libpyuhd.types.time_spec(np.uint64(t0_full),0.0)
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

    # transmit the code
    tx_stream=u.get_tx_stream(stream_args)
    tx_thread = threading.Thread(target=tx_send,args=(tx_stream,waveform,md))
    
    tx_thread.start()

    # do an swr measurement
    rx_thread = threading.Thread(target=rx_swr,args=(u,t0_full,swr_buffer))
    rx_thread.start()
    tx_thread.join()
    rx_thread.join()
    tx_stream=None
    
    
def main():
    """
    The main loop for the ionosonde transmitter
    """
    log=l.logger("tx-%d.log"%(time.time()))
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
    gl.sync_clock(usrp,log)
    
    # start with first frequency on tx and rx
    tune_req=uhd.libpyuhd.types.tune_request(s.freq(0))
    usrp.set_tx_freq(tune_req)
    usrp.set_rx_freq(tune_req)

    # setup enough repetitions of the code to fill a frequency step
    code_100 = 0.5*np.fromfile("waveforms/code-l10000-b10-000000f_100k.bin",dtype=np.complex64)
    code_50 = 0.5*np.fromfile("waveforms/code-l10000-b10-000000f_50k.bin",dtype=np.complex64)
    code_30 = 0.5*np.fromfile("waveforms/code-l10000-b10-000000f_30k.bin",dtype=np.complex64)    
    n_reps=s.freq_dur*sample_rate/len(code_100)
    data_100=np.tile(code_100,int(n_reps))
    data_50=np.tile(code_50,int(n_reps))
    data_30=np.tile(code_30,int(n_reps))

    # hold SWR measurement
    swr_buffer=np.empty(int(len(data_100)*0.5),dtype=n.complex64)    
     
    # figure out when to start the cycle
    t_now=usrp.get_time_now().get_real_secs()    
    t0=np.uint64(np.floor(t_now/(s.sweep_len_s))*s.sweep_len_s+s.sweep_len_s)
    print("starting next sweep at %1.2f"%(s.sweep_len_s))
    
    while True:
        log.log("Starting sweep at %1.2f"%(t0))
        for i in range(s.n_freqs):
            f0,dt=s.pars(i)
            
            bw=int(n.round(s.bw(i)*1e6))
            print("f=%f bandwidth %f"%(f0,bw))
            if bw == 50000:
                print("code 50 kHz")
                transmit_waveform(usrp,np.uint64(t0+dt),data_50,swr_buffer)
            elif bw == 30000:
                print("code 30 kHz")                                
                transmit_waveform(usrp,np.uint64(t0+dt),data_30,swr_buffer)
            else:
                print("code 100 kHz")
                # Transmit signal
                transmit_waveform(usrp,np.uint64(t0+dt),data_100,swr_buffer)
                
            
            # tune to next frequency 0.1 s before end
            tune_at(usrp,t0+dt+s.freq_dur-0.1,f0=s.freq(i+1))

            # check that GPS is still locked.
            gl.check_lock(usrp,log,exit_if_not_locked=True)

        t0+=np.uint64(s.sweep_len_s)

    
if __name__ == "__main__":
    main()
