#!/usr/bin/env python3
#
# Code adapted from digital rf.
#
# ----------------------------------------------------------------------------
# Copyright (c) 2017 Massachusetts Institute of Technology (MIT)
# All rights reserved.
#
# Distributed under the terms of the BSD 3-clause license.
#
# The full license is in the LICENSE file, distributed with this software.
# ----------------------------------------------------------------------------
"""
Script for analyzing pseudorandom-coded waveforms.

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

import numpy as np  # this is for those who can't cope with numpy as n
import numpy as n   # this saves one character of code each time
import scipy.signal
import scipy.fftpack as sf

import create_waveform


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


def create_estimation_matrix(code, rmin=0, rmax=1000):

    r_cache = periodic_convolution_matrix(envelope=code, rmin=rmin, rmax=rmax)
    A = r_cache['A']
    Ah = np.transpose(np.conjugate(A))
    # least-squares estimate
    # B=(A^H A)^{-1}A^H
    B_cache = np.dot(np.linalg.inv(np.dot(Ah, A)), Ah)

    r_cache['B'] = B_cache
    B_cached = True
    return(r_cache)


def analyze_prc2(z,
                 code,
                 cache_idx=0,
                 n_ranges=1000,
                 rfi_rem=False,
                 spec_rfi_rem=False,
                 cache=True,
                 gc_rem=False,
                 wfun=scipy.signal.tukey,
                 gc=20,
                 fft_filter=False,
                 time_variable_noise=False,
                 cw_rem=False):

    an_len=len(z)
    clen=len(code)
    N = int(an_len / clen)
    res = np.zeros([N, n_ranges], dtype=np.complex64)

    # use cached version of (A^HA)^{-1}A^H if it exists.
    cache_file="waveforms/cache-%d.h5" % (cache_idx)

    if os.path.exists(cache_file):
        with h5py.File(cache_file, "r") as hb:
            B=np.copy(hb["B"][()])
    else:
        r = create_estimation_matrix(code=code, rmax=n_ranges)
        B = r['B']
        with h5py.File(cache_file, "w") as hb:
            hb["B"]=B

    spec = np.zeros([N, n_ranges], dtype=np.complex64)

    z.shape=(N, clen)

    if cw_rem:
        for ri in np.arange(clen):
            z[:, ri]=z[:, ri]-np.mean(z[1:(N-1), ri])

    if rfi_rem:
        bg=np.median(z, axis=0)
        z=z-bg

    if fft_filter:
        S=np.zeros(clen, dtype=np.float32)
        for i in np.arange(N):
            S+=np.abs(sf.fft(z[i, :]))**2.0
        S=np.sqrt(S/float(N))
    for i in np.arange(N):
        # B=(A^H A)^{-1}A^H
        # B*z = (A^H A)^{-1}A^H*z = x_ml
        # z = measurement
        # res[i,:] = backscattered echo complex amplitude
        if fft_filter:
            zw=np.array(sf.ifft(sf.fft(z[i, :])/S), dtype=np.complex64)
        else:
            zw=z[i, :]
        res[i, :] = np.dot(B, zw)

    if gc_rem:
        for i in range(gc, n_ranges):
            res[:, i]=res[:, i]-np.median(res[:, i])

    if time_variable_noise:
        for i in np.arange(N):
            noise_amp=np.median(np.abs(res[i, :]))
            res[i, :]=res[i, :]/noise_amp

    window=1.0  # wfun(N)
    # ignore first and last, where frequency transition occurs
    res[0, :]=0.0
    res[N-1, :]=0.0
    for i in np.arange(n_ranges):
        spec[:, i] = np.fft.fftshift(np.fft.fft(
            window * res[:, i]
        ))

    spec_snr=np.zeros(spec.shape, dtype=np.float32)

    if spec_rfi_rem:
        median_spec = np.zeros(N, dtype=np.complex64)
        noise_floor = np.zeros(N, dtype=np.float32)
        spec_std = np.zeros(N, dtype=np.float32)

        for i in np.arange(N):
            median_spec[i] = np.median(spec[i, :])
            noise_floor[i] = np.median(np.abs(spec[i, :])**2.0)
            spec_std[i] = np.median(np.abs(spec[i, :]-median_spec[i]))

        for i in np.arange(n_ranges):
            # signal to noise ratio, frequency dependent
            spec_snr[:, i]= (np.abs(spec[:, i])**2.0-noise_floor)/noise_floor
            # noise standard deviation normalized power.
            spec[:, i] = (spec[:, i]-median_spec)/spec_std

    spec_snr[spec_snr < 0]=1e-3
    ret = {}
    ret['res'] = res
    ret['spec'] = spec
    ret['spec_snr'] = spec_snr
    return(ret)
