#!/usr/bin/env python3

import sweep
import h5py 
import numpy as n
import matplotlib.pyplot as plt

s=sweep.sweep(freqs=sweep.freqs30,freq_dur=2.0)

n_f=len(s.freqs)
h=h5py.File("spec.h5","r")
spec=h["spec"].value
freq=h["freq"].value

spec=spec-n.median(spec)
p_tot=n.sum(spec)
p_in=0.0
spec[n.where(freq < 2e6)[0]]=0
spec[n.where(freq > 19e6)[0]]=0
plt.plot(freq/1e6,10.0*n.log10(spec),color="black")
for fi in range(n_f):
    fidx=n.where( (freq > 1e6*s.freqs[fi][0])&(freq < 1e6*s.freqs[fi][1]))[0]
    p_in+=n.sum(spec[fidx])
    plt.plot(freq[fidx]/1e6,10.0*n.log10(spec[fidx]),color="green")
plt.title("Percent of power outside band %1.4f"%(100.0*(1-p_in/p_tot)))
plt.show()
    
