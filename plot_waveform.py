#!/usr/bin/env python3
#
# Simple script that allows you to plot the complex transmit waveform
# and the power spectrum of it.
#
import numpy as n
import matplotlib.pyplot as plt
import sys

bws=[30e3, 50e3, 100e3]

z=n.fromfile(sys.argv[1], dtype=n.complex64)
plt.subplot(211)
plt.title("Complex amplitude")
plt.plot(z.real)
plt.plot(z.imag)
plt.xlabel("Time (samples)")
plt.subplot(212)
fvec=n.fft.fftshift(n.fft.fftfreq(len(z), d=1/1e6))
plt.title("Power spectral density (dB)")


pwr_spec_lin=n.abs(n.fft.fftshift(n.fft.fft(z)))**2.0
for bw in bws:
    fidx=n.where(n.abs(fvec) <= bw/2.0)[0]
    P_in=n.sum(pwr_spec_lin[fidx])
    P_all=n.sum(pwr_spec_lin)
    print("power outside %1.2f kHz bandwidth = %1.3f percent" % (bw/1e3, (1.0-P_in/P_all)*100.0))

pwr_spec=10.0*n.log10(n.abs(n.fft.fftshift(n.fft.fft(z)))**2.0)
plt.plot(fvec/1e3, pwr_spec)

idx=n.where(pwr_spec < (n.nanmax(pwr_spec)-20.0))[0]
fidx=idx[n.argmax(pwr_spec[idx])]
plt.ylim([n.nanmax(pwr_spec)-120.0, n.nanmax(pwr_spec)+20])
plt.axvline(fvec[fidx]/1e3)
plt.xlabel("Frequency (kHz)")
plt.tight_layout()
plt.show()
# blah blah

# random seed = station number
