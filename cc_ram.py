#!/usr/bin/env python

import numpy as n
import matplotlib.pyplot as plt
import prc_lib as p
import glob
import os
import time
import re

import stuffr
import sweep
import h5py
import iono_config

def delete_old_files(t0,data_path="/dev/shm"):
    """
    Deleting files that are from the currently analyzed sweep or older.
    """
    # delete older files
    fl=glob.glob("%s/raw*.bin"%(data_path))
    fl.sort()
    for f in fl:
        try:
            tfile=int(re.search(".*/raw-(.*)-....bin",f).group(1))
            if tfile <= t0:            
                os.system("rm %s"%(f))
        except:
            print("error deleting file")

def analyze_latest_sweep(s,data_path="/dev/shm"):
    """
    Analyze an ionogram, make some plots, save some data
    """
    # figure out what cycle is ready
    t0=n.uint64(n.floor(time.time()/(s.sweep_len_s))*s.sweep_len_s-s.sweep_len_s)
    I=n.zeros([s.n_freqs,1000],dtype=n.float32)
    all_spec=n.zeros([s.n_freqs,20,1000],dtype=n.float32)
    dt=10000.0/100e3
    
    rvec=n.arange(1000.0)*1.5
    fvec=n.fft.fftshift(n.fft.fftfreq(20,d=dt))
    
    dname="%s/%s"%(iono_config.ionogram_path,stuffr.sec2dirname(t0))
    os.system("mkdir -p %s"%(dname))
    
    for i in range(s.n_freqs):
        fname="%s/raw-%d-%03d.bin"%(data_path,t0,i)
        if os.path.exists(fname):
            z=n.fromfile(fname,dtype=n.complex64)
            N=len(z)
#            print(len(z))
            res=p.analyze_prc(z,rfi_rem=False,spec_rfi_rem=False,dec=1)
 #           print(res["res"].shape)
            plt.subplot(121)
  #          print(dt)
            
            tvec=n.arange(N/10000.0)*dt
            dBr=10.0*n.log10(n.transpose(n.abs(res["res"])**2.0))
            noise_floor=n.nanmedian(dBr)
            dBr=dBr-noise_floor
            plt.pcolormesh(tvec,rvec,dBr,vmin=-3,vmax=n.max(dBr))
            plt.xlabel("Time (s)")
            plt.title("Range-Time Power f=%d (dB)\nnoise_floor=%1.2f (dB)"%(i,noise_floor))
            plt.ylabel("Range (km)")
            plt.ylim([0,500])
            
            
            plt.colorbar()
            plt.subplot(122)
            S=n.abs(res["spec"])**2.0
            all_spec[i,:,:]=S
            I[i,:]=n.max(S,axis=0)
            # normalize by median std estimate
#            I[i,:]=I[i,:]/n.median(n.abs(S-n.median(S)))
            dBs=10.0*n.log10(n.transpose(S))
            noise_floor=n.nanmedian(dBs)
            dBs=dBs-noise_floor
            plt.pcolormesh(fvec,rvec,dBs,vmin=-3,vmax=n.max(dBs))
            plt.ylim([0,500])
            
            plt.title("Range-Doppler Power (dB)\nnoise_floor=%1.2f (dB)"%(noise_floor))
            plt.xlabel("Frequency (Hz)")
            plt.ylabel("Range (km)")
            
            
            plt.colorbar()
            plt.tight_layout()
            
            plt.savefig("%s/iono-%d.png"%(dname,i))
            plt.close()
            plt.clf()
        else:
            return(0)
            print("file %s not found"%(fname))
    i_fvec=n.zeros(s.n_freqs)
    for fi in range(s.n_freqs):
        i_fvec[fi]=s.freq(fi)
    dB=10.0*n.log10(n.transpose(I))
    noise_floor=n.nanmedian(dB)
    plt.figure(figsize=(1.5*8,1.5*6))
    plt.pcolormesh(i_fvec/1e6,rvec,dB-noise_floor,vmin=-3,vmax=100.0)
    plt.title("Ionogram %s\nnoise_floor=%1.2f (dB)"%(stuffr.unix2datestr(t0),noise_floor))
    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Range (km)")
    plt.colorbar()
    plt.ylim([0,800.0])
    plt.tight_layout()
    ofname="%s/ionogram-%d.png"%(dname,t0)
    print("Saving ionogram %s"%(ofname))
    plt.savefig(ofname)
    plt.clf()
    plt.close()

    ho=h5py.File("%s/ionogram-%d.h5"%(dname,t0),"w")
    ho["I"]=I
    ho["i_freq_Hz"]=i_fvec
    ho["freq_Hz"]=fvec
    ho["range_km"]=rvec
    ho["spectra"]=all_spec
    ho["t0"]=t0
    ho.close()
    delete_old_files(t0)

if __name__ == "__main__":
    
    s=iono_config.s
    print("Starting analysis")
    analyze_latest_sweep(s)
