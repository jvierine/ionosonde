#!/usr/bin/env python3
#
# Simple script that allows you to plot the complex transmit waveform
# and the power spectrum of it.
#
import numpy as np
import matplotlib.pyplot as plt
import sys

bws=[30e3, 50e3, 100e3]

z=np.fromfile(sys.argv[1], dtype=np.complex64)
plt.subplot(211)
plt.title("Complex amplitude")
plt.plot(z.real)
plt.plot(z.imag)
plt.xlabel("Time (samples)")
plt.subplot(212)
fvec=np.fft.fftshift(np.fft.fftfreq(len(z), d=1/1e6))
plt.title("Power spectral density (dB)")


pwr_spec_lin=np.abs(np.fft.fftshift(np.fft.fft(z)))**2.0
for bw in bws:
    fidx=np.where(np.abs(fvec) <= bw/2.0)[0]
    P_in=np.sum(pwr_spec_lin[fidx])
    P_all=np.sum(pwr_spec_lin)
    print("power outside %1.2f kHz bandwidth = %1.3f percent" % (bw/1e3, (1.0-P_in/P_all)*100.0))

pwr_spec=10.0*np.log10(np.abs(np.fft.fftshift(np.fft.fft(z)))**2.0)
plt.plot(fvec/1e3, pwr_spec)

idx=np.where(pwr_spec < (np.nanmax(pwr_spec)-20.0))[0]
fidx=idx[np.argmax(pwr_spec[idx])]
plt.ylim([np.nanmax(pwr_spec)-120.0, np.nanmax(pwr_spec)+20])
plt.axvline(fvec[fidx]/1e3)
plt.xlabel("Frequency (kHz)")
plt.tight_layout()
plt.show()
# blah blah

# random seed = station number
