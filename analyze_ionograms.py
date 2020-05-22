#!/usr/bin/env python
import matplotlib
matplotlib.use("Agg")
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

def save_raw_data(fname="tmp.h5",
                  t0=0,
                  z_all=0,
                  freqs=0,
                  station=0,
                  sr=100e3,
                  freq_dur=4,
                  codes=[],
                  lat=78.1536,
                  lon=16.054,
                  code_type="perfect",
                  code_len=10000,
                  version=1):
    # 32 bit complex
    z_re=n.array(n.real(z_all),dtype=n.float16)
    z_im=n.array(n.imag(z_all),dtype=n.float16)
    print("saving %s"%(fname))
    ho=h5py.File(fname,"w")
    ho["z_re"]=z_re
    ho["t0"]=t0
    ho["z_im"]=z_im
    ho["freqs"]=freqs
    ho["codes"]=codes
    ho["code_type"]=code_type
    ho["freq_dur"]=freq_dur
    ho["sample_rate"]=sr
    ho["lat"]=lat
    ho["lon"]=lon
    ho["code_len"]=code_len
    ho["version"]=version
    ho["station_id"]=station
    ho.close()

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
    n_rg=iono_config.n_range_gates#g#2000
    t0=n.uint64(n.floor(time.time()/(s.sweep_len_s))*s.sweep_len_s-s.sweep_len_s)

    sfreqs=n.array(s.freqs)
    iono_freqs=0.5*(sfreqs[:,0]+sfreqs[:,1])
    fmax=n.max(iono_freqs)
    n_plot_freqs=int((fmax+0.5)/0.1)+1
    iono_p_freq=n.linspace(0,fmax+0.5,num=n_plot_freqs)
    I=n.zeros([n_plot_freqs,n_rg],dtype=n.float32)
    n_t=int(s.freq_dur/0.1)
    all_spec=n.zeros([s.n_freqs,n_t,n_rg],dtype=n.float32)
    dt=10000.0/100e3
    
    rvec=n.arange(float(n_rg))*1.5
    fvec=n.fft.fftshift(n.fft.fftfreq(n_t,d=dt))

    hdname=stuffr.unix2iso8601_dirname(t0)

    dname="%s/%s"%(iono_config.ionogram_path,hdname)
    os.system("mkdir -p %s"%(dname))

    z_all=n.zeros([s.n_freqs,int(s.freq_dur*100000)],dtype=n.complex64)
    
    for i in range(s.n_freqs):
        fname="%s/raw-%d-%03d.bin"%(data_path,t0,i)
        if os.path.exists(fname):
            z=n.fromfile(fname,dtype=n.complex64)
            z_all[i,:]=z
            N=len(z)
#            print(len(z))
            res=p.analyze_prc(z,rfi_rem=False,spec_rfi_rem=True,dec=1,code_type=iono_config.code_type,Nranges=n_rg)
 #           print(res["res"].shape)
            plt.subplot(121)
  #          print(dt)
            
            tvec=n.arange(N/10000.0)*dt
            dBr=10.0*n.log10(n.transpose(n.abs(res["res"])**2.0))
            noise_floor=n.nanmedian(dBr)
            dBr=dBr-noise_floor
            plt.pcolormesh(tvec,rvec,dBr,vmin=-3,vmax=30.0)
            plt.xlabel("Time (s)")
            plt.title("Range-Time Power f=%d (dB)\nnoise_floor=%1.2f (dB)"%(i,noise_floor))
            plt.ylabel("Range (km)")
            plt.ylim([0,500])
            
            
            plt.colorbar()
            plt.subplot(122)
            S=n.abs(res["spec"])**2.0

            sw=n.fft.fft(n.repeat(1.0/4,4),S.shape[0])
            for rg_id in range(S.shape[1]):
                S[:,rg_id]=n.roll(n.real(n.fft.ifft(n.fft.fft(S[:,rg_id])*sw)),-2)
            
            all_spec[i,:,:]=S
            pif=int(iono_freqs[i]/0.1)
            I[pif,:]+=n.max(S,axis=0)
            # normalize by median std estimate
#            I[i,:]=I[i,:]/n.median(n.abs(S-n.median(S)))
            dBs=10.0*n.log10(n.transpose(S))
            noise_floor=n.nanmedian(dBs)
            dBs=dBs-noise_floor
            plt.pcolormesh(fvec,rvec,dBs,vmin=-3,vmax=30.0)
            plt.ylim([0,500])
            
            plt.title("Range-Doppler Power (dB)\nnoise_floor=%1.2f (dB)"%(noise_floor))
            plt.xlabel("Frequency (Hz)")
            plt.ylabel("Range (km)")
            
            
            plt.colorbar()
            plt.tight_layout()
            
            plt.savefig("%s/iono-%03d.png"%(dname,i))
            plt.close()
            plt.clf()
        else:
            return(0)
            print("file %s not found"%(fname))
    i_fvec=n.zeros(s.n_freqs)
    for fi in range(s.n_freqs):
        i_fvec[fi]=s.freq(fi)
    dB=10.0*n.log10(n.transpose(I))
    dB[n.isinf(dB)]=n.nan
    noise_floor=n.nanmedian(dB)
    
    for i in range(dB.shape[1]):
        dB[:,i]=dB[:,i]-n.nanmedian(dB[:,i])
        
    dB[n.isnan(dB)]=-3
    
    plt.figure(figsize=(1.5*8,1.5*6))
    plt.pcolormesh(n.concatenate((iono_p_freq,[fmax+0.1])),rvec,dB,vmin=-3,vmax=20.0)
    plt.title("%s %s\nnoise_floor=%1.2f (dB)"%(iono_config.instrument_name,
                                               stuffr.unix2datestr(t0),
                                               noise_floor))
    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Range (km)")
    plt.colorbar()
    plt.ylim([0,800.0])
    plt.xlim([n.min(iono_freqs)-0.5,n.max(iono_freqs)+0.5])
    plt.tight_layout()

    datestr=stuffr.unix2iso8601(t0)

    ofname="%s/%s.png"%(dname,datestr)
    print("Saving ionogram %s"%(ofname))
    plt.savefig(ofname)
    plt.clf()
    plt.close()
    # make link to latest plot
    os.system("ln -sf %s latest.png"%(ofname))


    ofname="%s/ionogram-%d.h5"%(dname,t0)
    save_raw_data(ofname,
                  t0,
                  z_all,
                  s.freqs,
                  iono_config.station_id,
                  sr=100000,
                  freq_dur=s.freq_dur,
                  codes=s.codes,
                  lat=iono_config.lat,
                  lon=iono_config.lon,
                  code_type=iono_config.code_type)
                  
#    ho=h5py.File("%s/ionogram-%d.h5"%(dname,t0),"w")
 #   ho["I"]=I
#    ho["i_freq_Hz"]=i_fvec
 #   ho["freq_Hz"]=fvec
#    ho["range_km"]=rvec
 #   ho["spectra"]=all_spec
  #  ho["t0"]=t0
   # ho.close()
    
    delete_old_files(t0)

if __name__ == "__main__":
    
    s=iono_config.s
    print("Starting analysis")
    analyze_latest_sweep(s)
