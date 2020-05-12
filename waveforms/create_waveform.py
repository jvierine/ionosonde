#!python
# ----------------------------------------------------------------------------
# Copyright (c) 2017 Massachusetts Institute of Technology (MIT)
# All rights reserved.
#
# Distributed under the terms of the BSD 3-clause license.
#
# The full license is in the LICENSE file, distributed with this software.
# ----------------------------------------------------------------------------
"""Create pseudorandom-coded waveform files for sounding.

See the following paper for a description and application of meteor radar using
pseudorandom codes:

Vierinen, J., Chau, J. L., Pfeffer, N., Clahsen, M., and Stober, G.,
Coded continuous wave meteor radar, Atmos. Meas. Tech., 9, 829-839,
doi:10.5194/amt-9-829-2016, 2016.

"""
import math
from argparse import ArgumentParser

import numpy
import numpy as np
import scipy.signal


# seed is a way of reproducing the random code without
# having to store all actual codes. the seed can then
# act as a sort of station_id.
def create_pseudo_random_code(clen=10000, seed=0):
    numpy.random.seed(seed)
    phases = numpy.array(
        numpy.sign(numpy.random.randn(clen)),
        dtype=numpy.complex64,
    )
    return(phases)


# oversample a phase code by a factor of rep
def rep_seq(x, rep=10):
    L = len(x) * rep
    res = numpy.zeros(L, dtype=x.dtype)
    idx = numpy.arange(len(x)) * rep
    for i in numpy.arange(rep):
        res[idx + i] = x
    return(res)


#
# lets use 0.1 s code cycle and coherence assumption
# our transmit bandwidth is 100 kHz, and with a 10e3 baud code,
# that is 0.1 seconds per cycle as a coherence assumption.
# furthermore, we use a 1 MHz bandwidth, so we oversample by a factor of 10.
#
def waveform_to_file(station=0,
                     clen=10000,
                     oversample=10,
                     filter_output=False,
                     filter_factor=1.0):
    
    ofname='code-l%d-b%d-%06d.bin' % (clen, oversample, station)
    
    a = rep_seq(create_pseudo_random_code(clen=clen, seed=station),
                rep=oversample)
    
    if filter_output:
        w = numpy.zeros([oversample * clen], dtype=numpy.complex64)
        fl = (int(2*oversample*1.9*filter_factor)) # 100 kHz < 1% outside band
        w[0:fl] = scipy.signal.flattop(fl)
        print("Filter length %d samples"%(fl))
        # todo roll by fl
               
        aa = numpy.fft.ifft(numpy.fft.fft(w) * numpy.fft.fft(a))
        a = aa / numpy.max(numpy.abs(aa))
        a = numpy.array(a, dtype=numpy.complex64)
        # remove filter time shift 
        a=np.roll(a,-int(fl/2)+20)
        a.tofile(ofname)
        
    print("Writing file %s"%(ofname))
    a.tofile(ofname)


def barker_to_file(
    station=0, clen=10000, oversample=10, filter_output=False,
):
    a=np.zeros(clen*oversample,dtype=np.complex64)
    barker13=np.array([1,1,1,1,1,-1,-1,1,1,-1,1,-1,1],dtype=np.complex64)
    barker130=rep_seq(barker13,rep=oversample)
    a[0:130]=barker130
    print(len(a))
    w = numpy.zeros([oversample * clen], dtype=numpy.complex64)
    fl = (int(2*oversample))
    w[0:fl] = scipy.signal.blackmanharris(fl)
    aa = numpy.fft.ifft(numpy.fft.fft(w) * numpy.fft.fft(a))
    a = aa / numpy.max(numpy.abs(aa))
    a = numpy.array(a, dtype=numpy.complex64)
    a.tofile('code-barkerf.bin')



if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument(
        '-l', '--length', type=int, default=10000,
        help='''Code length (number of bauds). (default: %(default)s)''',
    )
    parser.add_argument(
        '-b', '--oversampling', type=int, default=10,
        help='''Oversampling factor (number of samples per baud).
                (default: %(default)s)''',
    )
    parser.add_argument(
        '-s', '--station', type=int, default=0,
        help='''Station ID (seed). (default: %(default)s)''',
    )
    parser.add_argument(
        '-f', '--filter', action='store_true',
        help='''Filter waveform with Blackman-Harris window.
                (default: %(default)s)''',
    )
    parser.add_argument(
        '-w', '--filter_factor', type=float, default=1.0,
        help='''Filter length factor (1 = 100 kHz, 2=50 kHz, 3.333=30 kHz
        (default: %(default)s)''',
    )

    op = parser.parse_args()

    waveform_to_file(
        station=op.station, clen=op.length, oversample=op.oversampling,
        filter_output=op.filter, filter_factor=op.filter_factor
    )
