#!/usr/bin/env python3
import numpy as n
import uhd
import scipy.signal as ss
import time
import matplotlib.pyplot as plt
import h5py
import sys


def acquire_spectrum(freq=12.5e6,
                     sample_rate=25e6,
                     N=250000,
                     N_windows=10000,
                     subdev="A:A",
                     ofname="spec.h5"):

    usrp = uhd.usrp.MultiUSRP("addr=%s,recv_buff_size=500000000"%(sys.argv[1]))
    subdev_spec=uhd.usrp.SubdevSpec(subdev)
    usrp.set_rx_subdev_spec(subdev_spec)

    # 100 Hz frequency resolution
    N=250000
    w=ss.blackmanharris(N)
    freqv=n.fft.fftshift(n.fft.fftfreq(N, d=1/25e6))+freq
    S=n.zeros(N)
    Nw=N_windows
    for i in range(Nw):
        print("%d/%d" % (i, Nw))
        samps = usrp.recv_num_samps(N, freq, 25000000, [0], 0)

        if len(samps[0]) == N:
            z=samps[0]
            z=z-n.mean(z)
            S+=n.abs(n.fft.fftshift(n.fft.fft(z*w)))**2.0
        else:
            print(len(samps[0]))
    #    time.sleep(1)
    with h5py.File(ofname, "w") as h:
        h["spec"]=S
        h["freq"]=freqv

    plt.plot(freqv/1e6, 10.0*n.log10(S))
    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Power spectral density (dB)")
    plt.show()


if __name__ == "__main__":
    acquire_spectrum(N_windows=100)
