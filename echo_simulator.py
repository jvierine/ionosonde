#!/usr/bin/env python
#
# Investigate code performance using the 
# error covariance matrix of the estimated complex
# radar scatter voltage
#
import numpy as n
import matplotlib.pyplot as plt
import h5py
import create_waveform
import prc_lib

# pseudorandom code
# code = create_waveform.create_pseudo_random_code(clen=10000, seed=0)

# randomized perfect code
code0 = create_waveform.create_pseudo_random_code(clen=10000, seed=0)
code1 = create_waveform.create_pseudo_random_code(clen=10000, seed=1)

# perfect code (not very good cross-correlation properties)
#code0=create_waveform.create_prn_dft_code(clen=10000,seed=0)
#code1=create_waveform.create_prn_dft_code(clen=10000,seed=1)

x=n.zeros(1000,dtype=n.complex64)
x[10]=1.0
x[900]=0.5
x[90]=-2.0
x[110]=4.0

r0=prc_lib.create_estimation_matrix(code0, rmin=0, rmax=1000)
r1=prc_lib.create_estimation_matrix(code1, rmin=0, rmax=1000)

A0=r0["A"]
A1=r1["A"]

m0=n.dot(A0,x)+n.random.randn(10000)+n.random.randn(10000)*1j

m1=n.dot(A1,x)+n.random.randn(10000)+n.random.randn(10000)*1j

xhat0=n.linalg.lstsq(A0,m0)[0]
print(xhat0)
plt.plot(xhat0.real)
plt.plot(xhat0.imag)
plt.show()

xhat1=n.linalg.lstsq(A1,m0)[0]
print(xhat1)
plt.plot(xhat1.real)
plt.plot(xhat1.imag)
plt.show()
