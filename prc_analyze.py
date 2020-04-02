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

import digital_rf as drf


def create_pseudo_random_code(clen=10000, seed=0):
    """
    seed is a way of reproducing the random code without
    having to store all actual codes. the seed can then
    act as a sort of station_id.

    """
    np.random.seed(seed)
    phases = np.array(
        #np.exp(1.0j * 2.0 * math.pi * np.random.random(clen)),
        np.sign(np.random.randn(clen)),
        dtype=np.complex64,
    )
    return(phases)


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


def analyze_prc(
        dirn='', channel='hfrx', idx0=0, an_len=1000000, clen=10000, station=0,
        Nranges=1000, rfi_rem=True, cache=True, dec=10
):
    r"""Analyze pseudorandom code transmission for a block of data.

    idx0 = start idx
    an_len = analysis length
    clen = code length
    station = random seed for pseudorandom code
    cache = Do we cache (\conj(A^T)\*A)^{-1}\conj{A}^T for linear least squares
        solution (significant speedup)
    rfi_rem = Remove RFI (whiten noise).

    """
    if type(dirn) is str:
        g = drf.DigitalRFReader(dirn)
    else:
        g = dirn

    code = create_pseudo_random_code(clen=clen, seed=station)
    N = an_len / clen
    res = np.zeros([N, Nranges], dtype=np.complex64)
    r = create_estimation_matrix(code=code, cache=cache, rmax=Nranges)
    B = r['B']
    spec = np.zeros([N, Nranges], dtype=np.complex64)

    for i in np.arange(N):
        z = stuffr.decimate(g.read_vector_c81d(idx0 + i * clen * dec, dec*clen, channel),dec=dec)
        z = z - np.median(z)  # remove dc

        # B=(A^H A)^{-1}A^H
        # B*z = (A^H A)^{-1}A^H*z = x_ml
        # z = measurement
        # res[i,:] = backscattered echo complex amplitude
        res[i, :] = np.dot(B, z)
    for i in np.arange(Nranges):
        spec[:, i] = np.fft.fftshift(np.fft.fft(
            scipy.signal.blackmanharris(N) * res[:, i]
        ))

    if rfi_rem:
        median_spec = np.zeros(N, dtype=np.float32)
        for i in np.arange(N):
            median_spec[i] = np.median(np.abs(spec[i, :]))
        for i in np.arange(Nranges):
            spec[:, i] = spec[:, i] / median_spec[:]
    ret = {}
    ret['res'] = res
    ret['spec'] = spec
    return(ret)


if __name__ == '__main__':
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    desc = """Script for analyzing pseudorandom-coded waveforms.

    See the following paper for a description and application of the technique:

    Vierinen, J., Chau, J. L., Pfeffer, N., Clahsen, M., and Stober, G.,
    Coded continuous wave meteor radar, Atmos. Meas. Tech., 9, 829-839,
    doi:10.5194/amt-9-829-2016, 2016.

    """

    parser = ArgumentParser(description=desc)

    parser.add_argument(
        'datadir', help='''Data directory to analyze.''',
    )
    parser.add_argument(
        '-c', '--ch', default='hfrx',
        help='''Channel name of data to analyze. (default: %(default)s)'''
    )
    parser.add_argument(
        '-o', '--out', dest='outdir', default='{datadir}/prc_analysis',
        help='''Processed output directory. (default: %(default)s)''',
    )
    parser.add_argument(
        '-x', '--delete_old', action='store_true', default=False,
        help='''Delete existing processed files.''',
    )
    parser.add_argument(
        '-n', '--analysis_length', dest='anlen', type=int, default=6000000,
        help='''Analysis length. (default: %(default)s)''',
    )
    parser.add_argument(
        '-l', '--code_length', dest='codelen', type=int, default=10000,
        help='''Code length. (default: %(default)s)''',
    )
    parser.add_argument(
        '-s', '--station', type=int, default=0,
        help='''Station ID for code (seed). (default: %(default)s)''',
    )
    parser.add_argument(
        '-r', '--nranges', type=int, default=1000,
        help='''Number of range gates. (default: %(default)s)''',
    )
    parser.add_argument(
        '-d', '--receiver_delay', type=int, default=0,
        help='''How much is receiver delayed. (default: %(default)s)''',
    )
    parser.add_argument(
        '-D', '--decimate', type=int, default=1,
        help='''How much to decimate signal. (default: %(default))''',
    )
    

    op = parser.parse_args()

    op.datadir = os.path.abspath(op.datadir)
    # join outdir to datadir to allow for relative path, normalize
    op.outdir = os.path.abspath(op.outdir.format(datadir=op.datadir))
    if not os.path.isdir(op.outdir):
        os.makedirs(op.outdir)
    datpath = os.path.join(op.outdir, 'last.dat')
    if op.delete_old:
        for f in itertools.chain(
            glob.iglob(datpath),
            glob.iglob(os.path.join(op.outdir, '*.png')),
        ):
            os.remove(f)

    d = drf.DigitalRFReader(op.datadir)
    sr = d.get_properties(op.ch)['samples_per_second']
    b = d.get_bounds(op.ch)
    idx = np.array(b[0])
    if os.path.isfile(datpath):
        fidx = np.fromfile(datpath, dtype=np.int)
        if b[0] <= fidx:
            idx = fidx

    while True:
        if idx + op.anlen*op.decimate > b[1]:
            print('waiting for more data, sleeping.')
            time.sleep(op.anlen*op.decimate / sr)
            b = d.get_bounds(op.ch)
            continue

        try:
            res = analyze_prc(
                d, channel=op.ch, idx0=idx+op.receiver_delay, an_len=op.anlen, clen=op.codelen,
                station=op.station, Nranges=op.nranges, dec=op.decimate,
                cache=True, rfi_rem=False,
            )
            plt.clf()
            timestamp=int(np.uint64(idx / sr))

            ho=h5py.File("%s/spec-%06d.h5"%(op.outdir,timestamp),"w")
            ho["range_doppler"]=res['spec']
            ho["range_amplitude"]=res['res']            
            ho.close()

            M = 10.0 * np.log10((np.abs(res['spec'])))
            plt.pcolormesh(np.transpose(M), vmin=(np.median(M) - 1.0))

            plt.colorbar()
            plt.title(
                datetime.datetime.utcfromtimestamp(idx / sr).strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
            )
            plt.savefig(os.path.join(
                op.outdir, 'spec-{0:06d}.png'.format(timestamp),
            ))
            print('%d' % (idx))
        except IOError:
            print('IOError, skipping.')
        idx = idx + op.anlen*op.decimate
        idx.tofile(datpath)
