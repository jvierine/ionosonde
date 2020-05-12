#!/usr/bin/env python3

import numpy as n

import sweep 

# sample rate for tx and rx
sample_rate=1000000

# minimum safe wait is 5 mins
#min_gps_lock_time=300
# reduced for testing
min_gps_lock_time=0

# sweep definition
# todo: add code definition here.
s=sweep.sweep(freqs=sweep.freqs30,
              codes=["waveforms/code-l10000-b10-000000f_100k.bin",
                     "waveforms/code-l10000-b10-000000f_50k.bin",
                     "waveforms/code-l10000-b10-000000f_30k.bin"],
              sample_rate=sample_rate,
              freq_dur=2.0)

# single frequency test
#s=sweep.sweep(freqs=[[4.6,4.65,0]],
#              codes=["waveforms/code-l10000-b10-000000f_100k.bin"],
#              freq_dur=60.0) # This is for OBW measurements

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
