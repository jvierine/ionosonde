#!/usr/bin/env python
#
# script that determines the delay between transmit and receive using
# simple cross-correlation
# (convolution of measured signal with conjugated version of transmitted signal)
#
import numpy as n
import digital_rf as drf
import matplotlib.pyplot as plt
import stuffr

# open data directory
d=drf.DigitalRFReader("/data/test")

# figure out how much data is in channel "hfrx"
b=d.get_bounds("hfrx")

# read code from file
code=n.fromfile("waveforms/code-l10000-b50-000044f.bin",dtype=n.complex64)

# calculate model cross-correlation
model_cc=n.abs(n.fft.fftshift(n.fft.ifft(n.fft.fft(code)*n.conj(n.fft.fft(code)))))
# normalize peak to 1
model_cc=model_cc/n.max(model_cc)

l=len(code)

n_steps=int((b[1]-b[0])/l)

# read vectors from data stream of the same length as the code.
for i in range(n_steps):
    # this should be one code length read from the data files.
    # digital rf
    z=d.read_vector_c81d(b[0]+i*l,l,"hfrx")
    
    # convolve code with measurement
    # figure out what this does:
    # - circular convolution in time domain is multiplication
    #   in discrete Fourier domain (FFT).
    # 
    cc=n.fft.ifft(n.fft.fft(z)*n.conj(n.fft.fft(code)))
    
    print("maximum cross-correlation at delay %d"%(n.argmax(n.abs(cc))))
    idx=n.arange(len(cc))-len(cc)/2
    meas_cc=n.fft.fftshift(n.abs(cc))
    meas_cc=meas_cc/n.max(meas_cc)
    plt.plot(idx,meas_cc,label="measured")
    plt.plot(idx,model_cc,label="expected")
    plt.legend()
    plt.show()

