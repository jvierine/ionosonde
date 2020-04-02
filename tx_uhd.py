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

def osync_clock(u):
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
    
def tune_at(u,t0,f0=4e6):
    """ tune radio to frequency f0 at t0_full """

#    u.clear_command_time()
    t0_ts=uhd.libpyuhd.types.time_spec(t0)
    print("tuning at %1.2f"%(t0_ts.get_real_secs()))
    u.set_command_time(t0_ts)
    tune_req=uhd.libpyuhd.types.tune_request(f0)
    u.set_tx_freq(tune_req)
    u.clear_command_time()

def transmit_waveform(u,t0_full,f0,waveform):
    t0_ts=uhd.libpyuhd.types.time_spec(np.uint64(t0_full),0.0)
    stream_args=uhd.usrp.libtypes.StreamArgs("fc32","sc16")
    md=uhd.types.TXMetadata()
    md.has_time_spec=True
    md.time_spec=t0_ts
    print("transmit start at %1.2f"%(t0_full))
#    tune_req=uhd.libpyuhd.types.tune_request(f0)
    # wait for moment right before transmit
    while t0_full-time.time() > 0.1:
        time.sleep(0.01)
    print(time.time())
#    u.set_tx_freq(tune_req)

    tx_stream=u.get_tx_stream(stream_args)
    # this command will block until everything is in the transmit
    # buffer.
    tx_stream.send(waveform,md,timeout=11.0)
    #print("done %1.2f"%(time.time()))

    
def main():
    """TX samples based on input arguments"""
    log=l.logger("tx-%d.log"%(time.time()))
    log.log("Starting TX sweep")
    
    # define an ionosonde program
    #s=sweep.sweep(freqs=sweep.freqs60,freq_dur=10.0)

    s=sweep.sweep(freqs=sweep.freqs30,freq_dur=2.0)
    
    sample_rate=1000000
    usrp = uhd.usrp.MultiUSRP()
    usrp.set_tx_rate(sample_rate)
    subdev_spec=uhd.usrp.SubdevSpec("A:A")
    usrp.set_tx_subdev_spec(subdev_spec)
    gl.sync_clock(usrp,log)
    # start with first frequency
    tune_req=uhd.libpyuhd.types.tune_request(s.freq(0))
    usrp.set_tx_freq(tune_req)


    code = np.fromfile("waveforms/code-l10000-b10-000000f.bin",dtype=np.complex64)
    n_reps=s.freq_dur*sample_rate/len(code)
    data=np.tile(code,int(n_reps))
     
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
            transmit_waveform(usrp,np.uint64(step_t0),f0,data)
            # tune to next frequency 0.1 s before end
            tune_at(usrp,step_t0+s.freq_dur-0.1,f0=s.freq(i+1))
            locked=gl.check_lock(usrp,log)
            if locked==False:
                log.log("Exiting due to loss of lock and restarting...")
                exit(0)

        t0+=np.uint64(s.sweep_len_s)

    print("started tx thread")

    
if __name__ == "__main__":
    main()
