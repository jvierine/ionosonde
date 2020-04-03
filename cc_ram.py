#!/usr/bin/env python

import numpy as n
import matplotlib.pyplot as plt
import prc_lib as p


code=n.fromfile("waveforms/code-l10000-b10-000000.bin",dtype=n.complex64)
for i in range(30):
    print(i)
    z=n.fromfile("/dev/shm/raw-%d.bin"%(i),dtype=n.complex64)
    N=len(z)
    print(len(z))
    if True:
        res=p.analyze_prc(z,rfi_rem=False,spec_rfi_rem=False,dec=1)
        print(res["res"].shape)
        plt.subplot(121)
        dt=10000.0/100e3
        print(dt)
        fvec=n.fft.fftshift(n.fft.fftfreq(N/10000,d=dt))
        rvec=n.arange(1000.0)*1.5
        tvec=n.arange(N/10000.0)*dt
        dBr=10.0*n.log10(n.transpose(n.abs(res["res"])**2.0))
        noise_floor=n.nanmedian(dBr)
        dBr=dBr-noise_floor
        plt.pcolormesh(tvec,rvec,dBr)
        plt.xlabel("Time (s)")
        plt.title("Range-Time Power f=%d (dB)\nnoise_floor=%1.2f (dB)"%(i,noise_floor))
        plt.ylabel("Range (km)")
        plt.ylim([0,500])
        
        
        plt.colorbar()
        plt.subplot(122)
        dBs=10.0*n.log10(n.transpose(n.abs(res["spec"])**2.0))
        noise_floor=n.nanmedian(dBs)
        dBs=dBs-noise_floor
        plt.pcolormesh(fvec,rvec,dBs)
        plt.ylim([0,500])
        plt.title("Range-Doppler Power (dB)\nnoise_floor=%1.2f (dB)"%(noise_floor))
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("Range (km)")
                        
                            
        plt.colorbar()
        plt.tight_layout()
        plt.savefig("iono-%d.png"%(i))
        plt.close()
        plt.clf()
#        plt.show()
    
#    cc=n.fft.ifft(n.conj(n.fft.fft(code,len(z)))*n.fft.fft(z))
 #   plt.plot(n.abs(cc[0:1000]),label="%d"%(i))
#plt.legend()
#plt.show()
