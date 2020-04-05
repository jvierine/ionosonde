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

# receiver subdevice
rx_subdev="A:A"
tx_subdev="A:0"

# this is where all the data produced by the ionosonde is stored
ionogram_path="./results"
