#!/usr/bin/env python3
import numpy as n
import uhd
import scipy.signal as ss
import time
import matplotlib.pyplot as plt
import h5py
usrp = uhd.usrp.MultiUSRP("recv_buff_size=500000000")
#usrp.set_rx_rate(25e6)
subdev_spec=uhd.usrp.SubdevSpec("A:A")
usrp.set_rx_subdev_spec(subdev_spec)
freq=12.5e6

#tune_req=uhd.libpyuhd.types.tune_request(freq)
#usrp.set_rx_freq(tune_req)

# 100 Hz frequency resolution
N=250000
w=ss.blackmanharris(N)
freqv=n.fft.fftshift(n.fft.fftfreq(N,d=1/25e6))+freq
S=n.zeros(N)
Nw=10000
for i in range(Nw):
    print("%d/%d"%(i,Nw))
    samps = usrp.recv_num_samps(N, freq, 25000000, [0], 0)
    
#    print(samps)
 #   print(len(samps))
    if len(samps[0]) == N:
        z=samps[0]
        z=z-n.mean(z)
        S+=n.abs(n.fft.fftshift(n.fft.fft(z*w)))**2.0
    else:
        print(len(samps[0]))
#    time.sleep(1)
h=h5py.File("spec.h5","w")
h["spec"]=S
h["freq"]=freqv
h.close()
plt.plot(freqv/1e6,10.0*n.log10(S))
plt.show()
    
