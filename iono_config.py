#!/usr/bin/env python3

import numpy as n
import sweep
import sys

import numpy as n
import os
try:
    import configparser
except ImportError as e:
    import configparser2 as configparser
    
import json
import create_waveform

class iono_config:
    def __init__(self,fname=None):
        c=configparser.ConfigParser()

        if fname != None:
            if os.path.exists(fname):
                print("reading %s"%(fname))
                c.read(fname)
            else:
                print("configuration file %s doesn't exist."%(fname))
                exit(0)
                
        self.fname=fname
        self.instrument_name=json.loads(c["config"]["instrument_name"])
        self.n_range_gates=int(json.loads(c["config"]["n_range_gates"]))
        self.station_id=json.loads(c["config"]["station_id"])

        self.lat=int(json.loads(c["config"]["lat"]))
        self.lon=int(json.loads(c["config"]["lon"]))        
        self.require_gps=bool(json.loads(c["config"]["require_gps"]))
        self.save_raw_voltage=bool(json.loads(c["config"]["save_raw_voltage"]))
        self.min_gps_lock_time=json.loads(c["config"]["min_gps_lock_time"])
        
        self.rx_channel=json.loads(c["config"]["rx_channel"])
        
        self.sample_rate=int(json.loads(c["config"]["sample_rate"]))
        self.dec=int(json.loads(c["config"]["dec"]))        
        
        self.data_dir=json.loads(c["config"]["data_dir"])
        
        self.range_shift=int(json.loads(c["config"]["range_shift"]))
        
#        self.codes=json.loads(c["config"]["codes"])
        self.short_name=json.loads(c["config"]["short_name"])

        self.code_len=json.loads(c["config"]["code_len"])        
        self.code_types=json.loads(c["config"]["code_type"])
        self.pulse_lengths=json.loads(c["config"]["pulse_length"])
        self.ipps=json.loads(c["config"]["ipp"])
        self.bws=json.loads(c["config"]["bw"])        

        print("Creating waveforms")
        self.n_codes=len(self.code_types)
        self.codes=[]
        self.orig_codes=[]
        for i in range(self.n_codes):
            cfname,ocode=create_waveform.waveform_to_file(station=self.station_id,
                                                          clen=self.code_len,
                                                          oversample=self.dec,
                                                          filter_output=True,
                                                          sr=self.sample_rate,
                                                          bandwidth=self.bws[i],
                                                          power_outside_band=0.01,
                                                          pulse_length=self.pulse_lengths[i],
                                                          ipp=self.ipps[i],
                                                          code_type=self.code_types[i])
            self.codes.append(cfname)
            self.orig_codes.append(ocode)

        self.freqs=json.loads(c["config"]["freqs"])
        self.n_freqs=len(self.freqs)
        for fi in range(len(self.freqs)):
            # center frequency
            self.freqs[fi][0]=float(self.freqs[fi][0])
            # code index
            self.freqs[fi][1]=int(self.freqs[fi][1])            
        
        self.transmit_amplitude=float(json.loads(c["config"]["transmit_amplitude"]))
        
        self.frequency_duration=json.loads(c["config"]["frequency_duration"])
        
        self.antenna_select_freq=float(json.loads(c["config"]["antenna_select_freq"]))

        self.gps_holdover_time=float(json.loads(c["config"]["gps_holdover_time"]))        
        
        self.tx_addr=json.loads(c["config"]["tx_addr"])
        self.rx_addr=json.loads(c["config"]["rx_addr"])
        
        self.tx_subdev=json.loads(c["config"]["tx_subdev"])
        self.rx_subdev=json.loads(c["config"]["rx_subdev"])
        
        self.ionogram_path=json.loads(c["config"]["ionogram_path"])
        
        self.reflected_power_cal_dB=json.loads(c["config"]["reflected_power_cal_dB"])

        try:
            os.mkdir(self.ionogram_path)
        except:
            pass
        
        if not os.path.exists(self.ionogram_path):
            print("Output directory %s doesn't exists and cannot be created"%(self.ionogram_path))
            exit(0)
        try:
            os.mkdir(self.ionogram_path)
        except:
            pass
        
        if not os.path.exists(self.data_dir):
            print("Output directory %s doesn't exists and cannot be created"%(self.data_dir))
            exit(0)

        self.s=sweep.sweep(freqs=self.freqs,
                           codes=self.codes,
                           sample_rate=self.sample_rate,
                           code_amp=self.transmit_amplitude,  # safe setting for waveform amplitude
                           freq_dur=self.frequency_duration)
            
    def __str__(self):
        out="Configuration\n"
        for e in dir(self):
            if not callable(getattr(self,e)) and not e.startswith("__"):
                out+="%s = %s\n"%(e,getattr(self,e))

        print("Sweep configuration")
        for i in range(self.n_freqs):
            out +="t=%1.2f s f=%1.2f MHz code=%s\n"%(i*self.frequency_duration,self.freqs[i][0],self.codes[self.freqs[i][1]])
        out+="Total ionogram durtion %1.2f s\n"%(self.n_freqs*self.frequency_duration)
        return(out)

    

def get_config():
    print(sys.argv)
    if len(sys.argv) != 2:
        print(len(sys.argv))
    c=iono_config(sys.argv[1])
    return(c)


if __name__ == "__main__":
    c=get_config()
    print(c)
