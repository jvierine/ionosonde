#!/usr/bin/env python
#
# Simple script that allows you to plot the complex transmit waveform
# and the power spectrum of it.
#
import numpy as n
import matplotlib.pyplot as plt
import sys

z=n.fromfile(sys.argv[1],dtype=n.complex64)
plt.subplot(211)
plt.title("Complex amplitude")
plt.plot(z.real)
plt.plot(z.imag)
plt.xlabel("Time (samples)")
plt.subplot(212)
fvec=n.fft.fftshift(n.fft.fftfreq(len(z),d=1/1e6))
plt.title("Power spectral density (dB)")
pwr_spec=10.0*n.log10(n.abs(n.fft.fftshift(n.fft.fft(z)))**2.0)
plt.plot(fvec/1e3,pwr_spec)

idx=n.where(pwr_spec < (n.nanmax(pwr_spec)-20.0))[0]
fidx=idx[n.argmax(pwr_spec[idx])]
plt.ylim([n.nanmax(pwr_spec)-120.0,n.nanmax(pwr_spec)+20])
plt.axvline(fvec[fidx]/1e3)
plt.xlabel("Frequency (kHz)")
plt.tight_layout()
plt.show()
# blah blah

# random seed = station number
