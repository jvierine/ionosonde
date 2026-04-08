#!/usr/bin/env python3
#
# An attempt to translate the main functionality my main
# R radio signal packages gursipr and stuffr to python.
# Nothing extremely complicated, just convenience functions
#
#
import numpy as np
import math
import matplotlib
import matplotlib.cbook
import matplotlib.pyplot as plt
import datetime
import time
import re
import pickle
import h5py
#from datetime import timezone
# fit_velocity
import scipy.constants
import scipy.optimize
import pytz


# xpath-like access to nested dictionaries
# @d ditct
# @q query (eg., /data/stuff)
def qd(d, q):
    keys = q.split('/')
    nd = d
    for k in keys:
        if k == '':
            continue
        if k in nd:
            nd = nd[k]
        else:
            return None
    return nd


# seed is a way of reproducing the random code without
# having to store all actual codes. the seed can then
# act as a sort of station_id.
def create_pseudo_random_code(len=10000, seed=0):
    np.random.seed(seed)
    phases = np.array(np.exp(1.0j*2.0*math.pi*np.random.random(len)),
                         dtype=np.complex64)
    return(phases)


def periodic_convolution_matrix(envelope, rmin=0, rmax=100):
    # we imply that the number of measurements is equal to the number of elements in code
    L = len(envelope)
    ridx = np.arange(rmin, rmax)
    A = np.zeros([L, rmax-rmin], dtype=np.complex64)
    for i in np.arange(L):
        A[i, :] = envelope[(i-ridx) % L]
    result = {}
    result['A'] = A
    result['ridx'] = ridx
    return(result)


def analyze_prc_file(fname="data-000001.gdf", clen=10000, station=0, Nranges=1000):
    z = np.fromfile(fname, dtype=np.complex64)
    code = create_pseudo_random_code(len=clen, seed=station)
    N = len(z)/clen
    res = np.zeros([N, Nranges], dtype=np.complex64)
    idx = np.arange(clen)
    r = create_estimation_matrix(code=code, cache=True)
    B = r['B']
    spec = np.zeros([N, Nranges], dtype=np.float32)

    for i in np.arange(N):
        res[i, :] = np.dot(B, z[idx + i*clen])
    for i in np.arange(Nranges):
        spec[:, i] = np.abs(np.fft.fft(res[:, i]))
    r['res'] = res
    r['spec'] = spec
    return(r)


B_cache = 0
r_cache = 0
B_cached = False


def create_estimation_matrix(code, rmin=0, rmax=1000, cache=True):
    global B_cache
    global r_cache
    global B_cached

    if cache == False or B_cached == False:
        r_cache = periodic_convolution_matrix(envelope=code, rmin=rmin, rmax=rmax)
        A = r_cache['A']
        Ah = np.transpose(np.conjugate(A))
        B_cache = np.dot(np.linalg.inv(np.dot(Ah, A)), Ah)
        r_cache['B'] = B_cache
        B_cached = True

    return(r_cache)


def grid_search1d(fun, xmin, xmax, nstep=100):
    vals = np.linspace(xmin, xmax, num=nstep)
    min_val=fun(vals[0])
    best_idx = 0
    for i in range(nstep):
        try_val = fun(vals[i])
        if try_val < min_val:
            min_val = try_val
            best_idx = i
    return(vals[best_idx])


def fit_velocity(z, t, var, frad=440.2e6):
    zz = np.exp(1.0j*np.angle(z))

    def ssfun(x):
        freq = 2.0*frad*x/scipy.constants.c
        model = np.exp(1.0j*2.0*scipy.constants.pi*freq*t)
        ss = np.sum((1.0/var)*np.abs(model-zz)**2.0)
        #        plt.plot( np.real(model))
        #plt.plot( np.real(zz), 'red')
        #plt.show()
        return(ss)

    v0 = grid_search1d(ssfun, -800.0, 800.0, nstep=50)

    #    v = scipy.optimize.fmin(ssfun,np.array([v0]),full_output=False,disp=False,retall=False)
    return(v0)


def fit_velocity_and_power(z, t, var, frad=440.2e6):
    zz = np.exp(1.0j*np.angle(z))

    def ssfun(x):
        freq = 2.0*frad*x/scipy.constants.c
        model = np.exp(1.0j*2.0*scipy.constants.pi*freq*t)
        ss = np.sum((1.0/var)*np.abs(model-zz)**2.0)
        return(ss)

    v0 = grid_search1d(ssfun, -800.0, 800.0, nstep=50)
    v0 = scipy.optimize.fmin(ssfun, np.array([v0]), full_output=False, disp=False, retall=False)
    freq = 2.0*frad*v0/scipy.constants.c
    dc = np.real(np.exp(-1.0j*2.0*scipy.constants.pi*freq*t)*z)
    p0 = (1.0/np.sum(1.0/var))*np.sum((1.0/var)*dc)

    return([v0, p0])


def dict2hdf5(d, fname):
    with h5py.File(fname, 'w') as f:
        for k in d.keys():
            f[k] = d[k]


def save_object(obj, filename):
    with open(filename, 'wb') as output:
        pickle.dump(obj, output, pickle.HIGHEST_PROTOCOL)


def load_object(filename):
    with open(filename, 'rb') as input:
        return(pickle.load(input))


def date2unix(year, month, day, hour, minute, second):
    t0=datetime.datetime(1970, 1, 1)
    t = datetime.datetime(year, month, day, hour, minute, second)
    return((t-t0).total_seconds())
#    t.replace(tzinfo=timezone.utc)
#    return(t.total_seconds())#imestamp())
#    return(time.mktime(t.timetuple()))


def unix2date(x):
    return datetime.datetime.utcfromtimestamp(x)


def unix2iso8601(t):
    return(unix2date(t).strftime("%Y-%m-%dT%H.%M.%SZ"))


def unix2iso8601_dirname(t, ic):
    return(unix2date(t).strftime(ic.ionogram_dirname))


def sec2dirname(t):
    return(unix2date(t).strftime("%Y-%m-%dT%H-00-00"))


def dirname2unix(dirn):
    r = re.search("(....)-(..)-(..)T(..)-(..)-(..)", dirn)
    return(date2unix(int(r.group(1)), int(r.group(2)), int(r.group(3)),
                     int(r.group(4)), int(r.group(5)), int(r.group(6))))


def unix2datestr(x):
    return(unix2date(x).strftime('%Y-%m-%d %H:%M:%S %Z'))


def compr(x, fr=0.001):
    sh = x.shape
    x = x.reshape(-1)
    xs = np.sort(x)
    mini = xs[int(fr*len(x))]
    maxi = xs[int((1.0-fr)*len(x))]
    mx = np.ones_like(x)*maxi
    mn = np.ones_like(x)*mini
    x = np.where(x < maxi, x, mx)
    x = np.where(x > mini, x, mn)
    x = x.reshape(sh)
    return(x)


def comprz(x):
    """ Compress signal in such a way that elements less than zero are set to zero. """
    zv = x*0.0
    return(np.where(x>0, x, zv))


def rep(x, n):
    """ interpolate """
    z = np.zeros(len(x)*n)
    for i in range(len(x)):
        for j in range(n):
            z[i*n+j]=x[i]
    return(z)


def comprz_dB(xx, fr=0.05):
    """ Compress signal in such a way that is logarithmic but also avoids negative values """
    x = np.copy(xx)
    sh = xx.shape
    x = x.reshape(-1)
    x = comprz(x)
    x = np.setdiff1d(x, np.array([0.0]))
    xs = np.sort(x)
    mini = xs[int(fr*len(x))]
    mn = np.ones_like(xx)*mini
    xx = np.where(xx > mini, xx, mn)
    xx = xx.reshape(sh)
    return(10.0*np.log10(xx))


def decimate(x, dec=2):
    """
    low pass filter and decimate
    """
    Nout = int(math.floor(len(x)/dec))
    idx = np.arange(Nout, dtype=np.int)*int(dec)
    res = x[idx]*0.0

    for i in np.arange(dec):
        res = res + x[idx+i]
    return(res/float(dec))


def decimate2(x, dec=2):
    Nout = int(math.floor(len(x)/dec))
    idx = np.arange(Nout, dtype=np.int)*int(dec)
    res = x[idx]*0.0
    count = np.copy(x[idx])
    count[:]=1.0

    count_vector = np.negative(np.isnan(x))*1.0
    x[np.where(np.isnan(x))] = 0.0

    for i in np.arange(dec):
        res = res + x[idx+i]
        count += count_vector[idx+i]

    count[np.where(count == 0.0)] = 1.0
    return(res/count)


def median_dec(x, dec=10):
    Nout = int(math.floor(len(x)/dec))
    idx = np.arange(dec)
    res = np.zeros([Nout], dtype=x.dtype)
    for i in np.arange(Nout):
        res[i] = np.median(x[i*dec + idx])
    return(res)


def decimate_mat(M, dec0=10, dec1=10):
    shape2 = [math.floor(M.shape[0]/dec0), math.floor(M.shape[1]/dec1)]
    M2 = np.zeros(shape2, dtype=M.dtype)
    for i in np.arange(shape2[0]):
        for j in np.arange(dec0):
            M2[i, :] = M2[i, :] + decimate(M[i+j, :], dec=dec1)
    return(M2)


def decimate_mat_max(M, dec0=10):
    shape2 = [int(np.floor(M.shape[0]/dec0)), int(M.shape[1])]
    M2 = np.zeros(shape2, dtype=M.dtype)
    idx = np.arange(dec0, dtype=np.int)
    for i in range(shape2[0]):
        for j in range(shape2[1]):
            M2[i, j] = np.max(M[i*dec0 + idx, j])
    return(M2)


def plot_cts(x, plot_abs=False, plot_show=True):
    time_vec = np.linspace(0, len(x)-1, num=len(x))
    plt.clf()
    plt.plot(time_vec, np.real(x), "blue")
    plt.plot(time_vec, np.imag(x), "red")
    if plot_abs:
        plt.plot(time_vec, np.abs(x), "black")
    if plot_show:
        plt.show()


def hanning(L=1000):
    n = np.linspace(0.0, L-1, num=L)
    return(0.5*(1.0-np.cos(2.0*scipy.constants.pi*n/L)))


def spectrogram(x, window=1024, wf=hanning):
    wfv = wf(L=window)
    Nwindow = int(math.floor(len(x)/window))
    res = np.zeros([Nwindow, window])
    for i in range(Nwindow):
        res[i, ] = np.abs(
            np.fft.fftshift(
                np.fft.fft(wfv*x[i*window + np.arange(window)])))**2
    return(res)
