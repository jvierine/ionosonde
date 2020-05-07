#!/usr/bin/env python3

import numpy as n

import sweep 

# sweep definition
# todo: add code definition here.
s=sweep.sweep(freqs=sweep.freqs30,freq_dur=2.0)

# ram disk to store about two ionosonde cycles worth of data
data_path="/dev/shm"

# sample rate for tx and rx
sample_rate=1000000

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
