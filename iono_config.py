#!/usr/bin/env python3

import numpy as n

import sweep 

# sample rate for tx and rx
sample_rate=1000000

instrument_name="UNIS Longyearbyen Ionosonde"
code_type="perfect"

n_range_gates=1000

station_id=0

lat=78.1536
lon=16.054


# minimum safe wait is 5 mins
#min_gps_lock_time=300
# gps acquisition time can be reduced for testing purposes
min_gps_lock_time=0

# sweep definition
# todo: add code definition here.

if True:
    s=sweep.sweep(freqs=sweep.freqs30,
                  codes=["waveforms/code-l10000-b10-000000f_100k.bin",
                         "waveforms/code-l10000-b10-000000f_50k.bin",
                         "waveforms/code-l10000-b10-000000f_30k.bin"],
                  sample_rate=sample_rate,
                  code_amp=0.5,  # safe setting for waveform amplitude
                  freq_dur=4.0)
    
# single frequency test
if False:
    s=sweep.sweep(freqs=[[4.6,4.7,0]],
                  codes=["waveforms/code-l10000-b10-000000f_50k.bin"],
                  code_amp=0.5,
                  freq_dur=60.0) # This is for OBW measurements

# ram disk to store about two ionosonde cycles worth of data
data_path="/dev/shm"


# IP address of the transmit USRP N210
tx_addr="192.168.20.2"
# IP address of the receive USRP N210 
rx_addr="192.168.10.2"

# transmit subdevice
tx_subdev="A:A"

# receiver subdevice
rx_subdev="A:A"

# this is where all the data produced by the ionosonde is stored
ionogram_path="./results"

# conversion from reflected power in ADC units to dBm
reflected_power_cal_dB=17.6 
