#!/usr/bin/env python3

import numpy as n

import sweep 


s=sweep.sweep(freqs=sweep.freqs30,freq_dur=2.0)
data_path="/dev/shm"
sample_rate=1000000
rx_subdev="A:A"

ionogram_path="./results"
