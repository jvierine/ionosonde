#!python
# ----------------------------------------------------------------------------
# Copyright (c) 2017 Massachusetts Institute of Technology (MIT)
# All rights reserved.
#
# Distributed under the terms of the BSD 3-clause license.
#
# The full license is in the LICENSE file, distributed with this software.
# ----------------------------------------------------------------------------
"""Script for analyzing pseudorandom-coded waveforms.

See the following paper for a description and application of the technique:

Vierinen, J., Chau, J. L., Pfeffer, N., Clahsen, M., and Stober, G.,
Coded continuous wave meteor radar, Atmos. Meas. Tech., 9, 829-839,
doi:10.5194/amt-9-829-2016, 2016.

"""
import datetime
import glob
import itertools
import math
import os
import time
import h5py
from argparse import ArgumentParser
import stuffr

import numpy as np
import scipy.signal
#import digital_rf as drf

import create_waveform 

#def create_pseudo_random_code(clen=10000, seed=0):
#    """
   # seed is a way of reproducing the random code without
  #  having to store all actual codes. the seed can then
 #   act as a sort of station_id.
#
  #  """
 #   np.random.seed(seed)
#    phases = np.array(
        #np.exp(1.0j * 2.0 * math.pi * np.random.random(clen)),
   #     np.sign(np.random.randn(clen)),
  #      dtype=np.complex64,
 #   )
#    return(phases)


def periodic_convolution_matrix(envelope, rmin=0, rmax=100):
    """
    we imply that the number of measurements is equal to the number of elements
    in code

    """
    L = len(envelope)
    ridx = np.arange(rmin, rmax)
    A = np.zeros([L, rmax-rmin], dtype=np.complex64)
    for i in np.arange(L):
        A[i, :] = envelope[(i-ridx) % L]
    result = {}
    result['A'] = A
    result['ridx'] = ridx
    return(result)


B_cache = 0
r_cache = 0
B_cached = False
def create_estimation_matrix(code, rmin=0, rmax=1000, cache=True):
    global B_cache
    global r_cache
    global B_cached

    if not cache or not B_cached:
        r_cache = periodic_convolution_matrix(
            envelope=code, rmin=rmin, rmax=rmax,
        )
        A = r_cache['A']
        Ah = np.transpose(np.conjugate(A))
        # least-squares estimate
        # B=(A^H A)^{-1}A^H
        B_cache = np.dot(np.linalg.inv(np.dot(Ah, A)), Ah)
        
        r_cache['B'] = B_cache
        B_cached = True
        return(r_cache)
    else:
        return(r_cache)


def analyze_prc(zin,
                clen=10000,
                station=0,
                Nranges=1000,
                rfi_rem=True,
                spec_rfi_rem=False,
                cache=True,
                gc_rem=True,
#                wfun=scipy.signal.blackmanharris(N),
                wfun=scipy.signal.tukey,
#                wfun=1.0,
                gc=20,
                dec=10):
    """
    Analyze pseudorandom code transmission for a block of data.

    idx0 = start idx
    an_len = analysis length
    clen = code length
    station = random seed for pseudorandom code
    cache = Do we cache (\conj(A^T)\*A)^{-1}\conj{A}^T for linear least squares
        solution (significant speedup)
    rfi_rem = Remove RFI (whiten noise).

    """
    code = create_waveform.create_pseudo_random_code(clen=clen, seed=station)
    an_len=len(zin)/dec
    N = int(an_len / clen )
    res = np.zeros([N, Nranges], dtype=np.complex64)
    if os.path.exists("waveforms/b-%d-%d.h5"%(station,Nranges)):
        hb=h5py.File("waveforms/b-%d-%d.h5"%(station,Nranges),"r")
        B=hb["B"].value
        hb.close()
    else:
        r = create_estimation_matrix(code=code, cache=cache, rmax=Nranges)
        B = r['B']        
        hb=h5py.File("waveforms/b-%d-%d.h5"%(station,Nranges),"w")
        hb["B"]=B
        hb.close()        
        
    spec = np.zeros([N, Nranges], dtype=np.complex64)

    if dec > 1:
        z=stuffr.decimate(zin,dec=dec)
    else:
        z=zin
    z.shape=(N,clen)
    if rfi_rem:
        bg=np.median(z,axis=0)
        z=z-bg
#    print(len(z))
    for i in np.arange(N):
#        z = stuffr.decimate(zin[(i*clen*dec):((i+1)*clen*dec)],dec=dec)
        # B=(A^H A)^{-1}A^H
        # B*z = (A^H A)^{-1}A^H*z = x_ml
        # z = measurement
        # res[i,:] = backscattered echo complex amplitude
        res[i, :] = np.dot(B, z[i,:])
    if gc_rem:
        for i in range(gc,Nranges):
            res[:,i]=res[:,i]-np.median(res[:,i])

    window=wfun(N)
    for i in np.arange(Nranges):
        spec[:, i] = np.fft.fftshift(np.fft.fft(
            window * res[:, i]
        ))

    if spec_rfi_rem:
        median_spec = np.zeros(N, dtype=np.float32)
        for i in np.arange(N):
            median_spec[i] = np.median(np.abs(spec[i, :]))
        for i in np.arange(Nranges):
            spec[:, i] = spec[:, i] / median_spec[:]
    ret = {}
    ret['res'] = res
    ret['spec'] = spec
    return(ret)


