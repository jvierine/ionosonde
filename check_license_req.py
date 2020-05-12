#!/usr/bin/env python3
#
# Simple spectrum analyzer to measure the transmitted spectrum
# to check that the transmitter meets frequency licensing requirements.
#
import sweep
import h5py 
import numpy as n
import matplotlib.pyplot as plt

acquire_new_spec=True

if acquire_new_spec:
    import analyze_spectrum as aspec

s=sweep.sweep(freqs=sweep.freqs30,freq_dur=2.0)

n_f=len(s.freqs)

if acquire_new_spec:
    print("Measuring receiver noise floor. Make sure the transmitter is powered off")
    aspec.acquire_spectrum(ofname="meas/spec_off.h5",N_windows=1000)
    
    try:
        input("Measuring the transmitted spectrum. Make sure that the transmitter is on.\nPress any key to continue.")
    except:
        pass

    aspec.acquire_spectrum(ofname="meas/spec_on.h5",N_windows=10000)
    

# this file contains no transmit
ho=h5py.File("meas/spec_off.h5","r")
noise_floor=ho["spec"].value/1000.0 # 1000 measurements
# this one contains transmit
if acquire_new_spec:
    h=h5py.File("meas/spec_on.h5","r")
else:
    h=h5py.File("meas/spec_on_pa_22.6dBm.h5","r")
    
spec=h["spec"].value/10000.0  # 10000 measurements
freq=h["freq"].value

# substract noise floor
spec=spec-noise_floor
p_in=0.0
spec[n.where(freq < 2e6)[0]]=0
spec[n.where(freq > 19e6)[0]]=0
p_tot=n.sum(spec)

plt.plot(freq/1e6,10.0*n.log10(spec),color="black")
for fi in range(n_f):
    fidx=n.where( (freq > 1e6*s.freqs[fi][0])&(freq < 1e6*s.freqs[fi][1]))[0]
    p_in+=n.sum(spec[fidx])
    plt.plot(freq[fidx]/1e6,10.0*n.log10(spec[fidx]),color="green")
plt.title("Power outside licensed band %1.4f %%"%(100.0*(1-p_in/p_tot)))
plt.xlabel("Frequency (MHz)")
plt.ylabel("Power (dB)")
plt.show()
    
