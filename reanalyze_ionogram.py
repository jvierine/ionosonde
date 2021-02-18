#!/usr/bin/env python3
import numpy as n
import h5py
import matplotlib.pyplot as plt
import scipy.constants as c
import os

import create_waveform
import stuffr
import iono_config

def incoh_an(z,code,nr=500):
    code_len=len(code)
    S=n.zeros([nr,code_len])
#    C=n.conj(n.fft.fft(code))
    for ci in range(z.shape[0]):
        for ri in range(nr):
            tidx=n.array(n.mod(n.arange(code_len)+ri,code_len),dtype=n.int)
            S[ri,:]+=n.fft.fftshift(n.abs(n.fft.fft(z[ci,tidx]*n.conj(code)))**2.0)
#    for fi in range(code_len):
 #       S[:,fi]=S[:,fi]-n.median(S[:,fi])
    return(S)
        

def analyze_ionogram(fname="/home/markus/j/ionosonde/results/2020-05-22T09:00:00Z/raw-2020-05-22T09:30:00.h5",
                     avg_spec=False,
                     plot_ionogram=False,
                     plot_spectra=False,
                     use_old=False,
                     max_range=1000,
                     min_range=0,
                     version=1,
                     ic=iono_config.get_config()):


    h=h5py.File(fname,"r")

    t0=h["t0"].value
    hdname=stuffr.unix2iso8601_dirname(h["t0"].value)
    dname="%s/%s"%(ic.ionogram_path, hdname)
    os.system("mkdir -p %s"%(dname))
    datestr=stuffr.unix2iso8601(t0)            
    iono_ofname="%s/ionogram-%s.h5"%(dname,datestr)
    print("looking for %s"%(iono_ofname))
    if use_old:
        if os.path.exists(iono_ofname):
            hi=h5py.File(iono_ofname,"r")
            I=n.copy(hi["I"].value)
            r=n.copy(hi["I_rvec"].value)
            f=n.copy(hi["I_fvec"].value)
            hi.close()
            return(I,r,f)


    if not "version" in h.keys():
        print("Not correction file version")
        h.close()
        return
    
    if h["version"].value != version:
        print("Not correct file version")
        h.close()
        return

#    if use_old:
#        if "I" in h.keys():
#            I=n.copy(h["I"].value)
#            I_fvec=n.copy(h["I_fvec"].value)
#            I_rvec=n.copy(h["I_rvec"].value)
#            h.close()
#            return(I,I_rvec,I_fvec)
        
    
    # float16 re and im to complex64
    z_all=n.array(h["z_re"].value+h["z_im"].value*1j,dtype=n.complex64)
    freqs=h["freqs"].value
    codes=h["codes"].value
    code_type=h["code_type"].value
    if "code_len" in h.keys():
        code_len=h["code_len"].value
    else:
        code_len=10000
#    print(codes)
    sample_rate=h["sample_rate"].value
    dr=c.c/h["sample_rate"].value/2.0/1e3
    t0=h["t0"].value
    n_freqs=freqs.shape[0]
    if "station_id" in h.keys():
        station_id=h["station_id"].value
    else:
        station_id=0

    iono_freqs=0.5*(freqs[:,0]+freqs[:,1])
    fmax=n.max(iono_freqs)
    n_plot_freqs=int((fmax+0.5)/0.1)+1
    iono_p_freq=n.linspace(0,fmax+0.5,num=n_plot_freqs)
    I=n.zeros([n_plot_freqs,code_len],dtype=n.float32)
    

    wf=create_waveform.create_prn_dft_code(clen=code_len,seed=station_id)
    WF=n.fft.fft(wf)
    rvec=n.arange(code_len)*dr

    IS=n.zeros([n_freqs,code_len])

    for i in range(n_freqs):
        z=n.copy(z_all[i,:])
        z=z-n.mean(z)

        
        N_codes=len(z)/code_len
        z.shape=(N_codes,code_len)

        echoes=n.zeros([N_codes,code_len],dtype=n.complex64)
        spec=n.zeros([N_codes,code_len],dtype=n.float)
        
        for ci in range(N_codes):
            echoes[ci,:]=n.fft.ifft(n.fft.fft(z[ci,:])/WF)
            
        # remove edge effect when hopping in frequency
        echoes[N_codes-1,:]=echoes[N_codes-2,:]
        
        for ri in range(code_len):
            spec[:,ri]=n.fft.fftshift(n.abs(n.fft.fft(echoes[:,ri]))**2.0)
        for fi in range(N_codes):
            spec[fi,:]=spec[fi,:]/n.median(n.abs(spec[fi,:]))

        if avg_spec:
            sw=n.fft.fft(n.repeat(1.0/4,4),N_codes)
            for ri in range(code_len):
                spec[:,ri]=n.roll(n.real(n.fft.ifft(n.fft.fft(spec[:,ri])*sw)),-2)
        pif=int(iono_freqs[i]/0.1)
        I[pif,:]+=n.max(spec,axis=0)
        IS[i,:]=n.max(spec,axis=0)

        if plot_spectra:
            tv=n.arange(N_codes)
            dBP=n.transpose(10.0*n.log10(n.abs(echoes)**2.0))
            nf=n.nanmedian(dBP)
            plt.pcolormesh(tv,rvec,dBP,vmin=nf,vmax=nf+20)
            plt.ylim([0,800])
            plt.colorbar()
            plt.show()
            dBS=n.transpose(10.0*n.log10(spec))
            nf=n.nanmedian(dBS)
            dop=3e8*n.fft.fftshift(n.fft.fftfreq(N_codes,d=code_len/float(sample_rate)))/2.0/(freqs[i,0]*1e6)
            plt.pcolormesh(dop,rvec,dBS,vmin=nf,vmax=nf+20)
            plt.xlabel("Doppler shift (m/s)")
            plt.ylabel("Range (km)")
            plt.ylim([0,800])
            plt.colorbar()
            plt.show()

    if plot_ionogram:
        dBI=n.transpose(10.0*n.log10(I))
        dBI[n.isinf(dBI)]=n.nan
        noise_floor=n.nanmedian(dBI)    
        dBI=dBI-noise_floor
        dBI[n.isnan(dBI)]=-3
        plt.pcolormesh(n.concatenate((iono_p_freq,[fmax+0.1])),rvec,dBI,vmin=-3,vmax=20.0)
        plt.title("%s %s\nNoise floor=%1.2f (dB)"%(ic.instrument_name,
                                                   stuffr.unix2datestr(h["t0"].value),
                                                   noise_floor))

        plt.xlim([n.min(iono_freqs)-0.5,n.max(iono_freqs)+0.5])    
        #    plt.pcolormesh(freqs[:,0],rvec,dBI,vmin=0,vmax=20)
        plt.ylim([0,800])
        plt.colorbar()
        plt.xlabel("Frequency (MHz)")
        plt.ylabel("Virtual range (km)")
        plt.tight_layout()
        ofname="%s/%s.png"%(dname,datestr)
        print("Saving ionogram %s"%(ofname))
        plt.savefig(ofname)
        plt.clf()
        plt.close()

    print("Saving ionogram %s"%(iono_ofname))
    
    ho=h5py.File(iono_ofname,"w")
    ho["I"]=IS
    ho["I_rvec"]=rvec
    ho["t0"]=h["t0"].value
    ho["lat"]=h["lat"].value
    ho["lon"]=h["lon"].value
    ho["I_fvec"]=freqs
    ho["ionogram_version"]=1
    ho.close()
    h.close()
    return(IS,rvec,freqs)
                            
        
if __name__ == "__main__":
    ic = iono_config.get_config(write_waveforms=False)
    I,rvec,freq=analyze_ionogram(fname="results/2020-05-21T16-00-00/ionogram-1590076920.h5",
                                 avg_spec=False,
                                 plot_ionogram=False,
                                 plot_spectra=False,
                                 version=1,
                                 ic)

