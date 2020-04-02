#!/usr/bin/env python

import numpy as n
import matplotlib.pyplot as plt
import prc_lib as p


code=n.fromfile("waveforms/code-l10000-b10-000000.bin",dtype=n.complex64)
for i in range(6):
    print(i)
    z=n.fromfile("/dev/shm/raw-%d.bin"%(i),dtype=n.complex64)
    if len(z) == 9000000:
        res=p.analyze_prc(z,rfi_rem=True,spec_rfi_rem=True)
        plt.subplot(121)
        dt=10000.0/100e3
        fvec=n.fft.fftshift(n.fft.fftfreq(len(z)/100000,d=dt))
        rvec=n.arange(1000.0)*1.5
        tvec=n.arange(9000000/100000.0)*dt
        dBr=10.0*n.log10(n.transpose(n.abs(res["res"])**2.0))
        dBr=dBr-n.nanmedian(dBr)
        plt.pcolormesh(tvec,rvec,dBr)
        plt.xlabel("Frequency (Hz)")
        plt.title("Range-Time Power f=%d (dB)"%(i))
        plt.ylabel("Range (km)")
        plt.ylim([0,500])
        
        
        plt.colorbar()
        plt.subplot(122)
        dBs=10.0*n.log10(n.transpose(n.abs(res["spec"])**2.0))
        dBs=dBs-n.nanmedian(dBs)
        plt.pcolormesh(fvec,rvec,dBs)
        plt.ylim([0,500])
        plt.title("Range-Doppler Power (dB)")
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("Range (km)")
                        
                            
        plt.colorbar()

        plt.show()
    
#    cc=n.fft.ifft(n.conj(n.fft.fft(code,len(z)))*n.fft.fft(z))
 #   plt.plot(n.abs(cc[0:1000]),label="%d"%(i))
#plt.legend()
#plt.show()
