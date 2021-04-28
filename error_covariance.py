#!/usr/bin/env python3
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
code = create_waveform.create_pseudo_random_code(clen=10000, seed=0)

# randomized perfect code
#code=create_waveform.create_prn_dft_code(clen=10000,seed=0)
plt.plot(code.real)
plt.plot(code.imag)
plt.show()

r=prc_lib.create_estimation_matrix(code, rmin=0, rmax=1000)

A=r["A"]

# a posteriory covariance matrix
S=n.linalg.inv(n.dot(n.conj(n.transpose(A)), A))

plt.figure(figsize=(10, 6))
plt.subplot(121)
plt.plot(n.diag(S)*10000.0)
plt.title("A posteriori estimation error variance")
plt.xlabel("Range gate")
plt.ylabel("Normalized a posteriori error variance")
#plt.axhline(1/10000.0,color="gray")

plt.subplot(122)
plt.title("Error covariance matrix row 500")
plt.plot(S[500, :].real)
plt.plot(S[500, :].imag)
plt.xlabel("Range gate")
plt.ylabel("Error covariance")
plt.tight_layout()
plt.show()
