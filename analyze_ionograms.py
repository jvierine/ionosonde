#!/usr/bin/env python3
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
import scipy.constants as c

def save_raw_data(fname="tmp.h5",
                  t0=0,
                  z_all=0,
                  freqs=0,
                  station=0,
                  sr=100e3,
                  freq_dur=4):

    """
    save all relevant information that will allow an ionogram
    and range-Doppler spectra to be calculated
    """
    # 32 bit complex
    z_re=n.array(n.real(z_all),dtype=n.float16)
    z_im=n.array(n.imag(z_all),dtype=n.float16)
    print("saving raw complex voltage %s"%(fname))
    ho=h5py.File(fname,"w")
    ho["z_re"]=z_re
    ho["t0"]=t0
    ho["z_im"]=z_im
    ho["freqs"]=freqs
    ho["freq_dur"]=freq_dur
    ho["sample_rate"]=sr
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

def analyze_latest_sweep(ic,data_path="/dev/shm"):
    """
    Analyze an ionogram, make some plots, save some data
    """
    # TODO: save raw voltage to file,
    # then analyze raw voltage file with common program
    # figure out what cycle is ready
    s=ic.s
    n_rg=ic.n_range_gates
    t0=n.uint64(n.floor(time.time()/(s.sweep_len_s))*ic.s.sweep_len_s-ic.s.sweep_len_s)

    sfreqs=n.array(ic.s.freqs)
    iono_freqs=sfreqs[:,0]
    fmax=n.max(iono_freqs)
    n_plot_freqs=int((fmax+0.5)/0.1)+1
    iono_p_freq=n.linspace(0,fmax+0.5,num=n_plot_freqs)
    I=n.zeros([n_plot_freqs,n_rg],dtype=n.float32)
    IS=n.zeros([sfreqs.shape[0],n_rg],dtype=n.float32)

    # number of transmit "pulses"
    n_t=int(ic.s.freq_dur*1000000/(ic.code_len*ic.dec))

    all_spec=n.zeros([ic.s.n_freqs,n_t,n_rg],dtype=n.float32)

    # IPP length
    dt=ic.dec*ic.code_len/1e6

    # range step
    dr = ic.dec*c.c/ic.sample_rate/2.0/1e3

    rvec=n.arange(float(n_rg))*dr
    fvec=n.fft.fftshift(n.fft.fftfreq(n_t,d=dt))

    hdname=stuffr.unix2iso8601_dirname(t0, ic)
    dname="%s/%s"%(ic.ionogram_path,hdname)
    os.system("mkdir -p %s"%(dname))

    z_all=n.zeros([ic.s.n_freqs,int(ic.s.freq_dur*100000)],dtype=n.complex64)

    noise_floors=[]

    for i in range(ic.s.n_freqs):
        fname="%s/raw-%d-%03d.bin"%(data_path,t0,i)
        if os.path.exists(fname):
            z=n.fromfile(fname,dtype=n.complex64)
            z_all[i,:]=z
            N=len(z)
            code_idx=ic.s.code_idx(i)
            res=p.analyze_prc2(z,
                               code=ic.orig_codes[code_idx],
                               cache_idx=code_idx,
                               rfi_rem=False,
                               spec_rfi_rem=True,
                               n_ranges=n_rg)

            plt.figure(figsize=(1.5*8,1.5*6))
            plt.subplot(121)

            tvec=n.arange(int(N/ic.code_len),dtype=n.float64)*dt
            dBr=10.0*n.log10(n.transpose(n.abs(res["res"])**2.0))
            noise_floor=n.nanmedian(dBr)
            noise_floor_0=noise_floor
            noise_floors.append(noise_floor_0)
            dBr=dBr-noise_floor
            dB_max=n.nanmax(dBr)
            plt.pcolormesh(tvec,rvec-ic.range_shift*dr,dBr,vmin=-3,vmax=ic.max_plot_dB)
            plt.xlabel("Time (s)")
            plt.title("Range-Time Power f=%d (dB)\nnoise_floor=%1.2f (dB) peak SNR=%1.2f"%(i,noise_floor,dB_max))
            plt.ylabel("Range (km)")
            plt.ylim([-10,ic.max_plot_range])


            plt.colorbar()
            plt.subplot(122)
            S=n.abs(res["spec"])**2.0

            #sw=n.fft.fft(n.repeat(1.0/4,4),S.shape[0])
            #for rg_id in range(S.shape[1]):
            #    S[:,rg_id]=n.roll(n.real(n.fft.ifft(n.fft.fft(S[:,rg_id])*sw)),-2)

            all_spec[i,:,:]=S
            # 100 kHz steps for ionogram freqs
            pif=int(iono_freqs[i]/0.1)
            I[pif,:]+=n.max(S,axis=0)
            IS[i,:]=n.max(S,axis=0)

            # normalize by median std estimate
#            I[i,:]=I[i,:]/n.median(n.abs(S-n.median(S)))
            dBs=10.0*n.log10(n.transpose(S))
            noise_floor=n.nanmedian(dBs)
            dBs=dBs-noise_floor
            max_dB=n.nanmax(dBs)
            plt.pcolormesh(fvec,rvec-ic.range_shift*dr,dBs,vmin=-3,vmax=ic.max_plot_dB)
            plt.ylim([-10,ic.max_plot_range])

            plt.title("Range-Doppler Power (dB)\nnoise_floor=%1.2f (dB) peak SNR=%1.2f (dB)"%(noise_floor,max_dB))
            plt.xlabel("Frequency (Hz)")
            plt.ylabel("Virtual range (km)")


            plt.colorbar()
            plt.tight_layout()

            plt.savefig("%s/iono-%03d.png"%(dname,i))
            plt.close()
            plt.clf()
        else:
            return(0)
            print("file %s not found"%(fname))

    i_fvec=n.zeros(ic.s.n_freqs)
    for fi in range(ic.s.n_freqs):
        i_fvec[fi]=s.freq(fi)
    dB=10.0*n.log10(n.transpose(I))
    dB[n.isinf(dB)]=n.nan
    noise_floor=n.nanmedian(dB)

    for i in range(dB.shape[1]):
        dB[:,i]=dB[:,i]-n.nanmedian(dB[:,i])

    dB[n.isnan(dB)]=-3

    noise_floor_0=n.mean(n.array(noise_floors))

    plt.figure(figsize=(1.5*8,1.5*6))
    max_dB=n.nanmax(dB)
    plt.pcolormesh(n.concatenate((iono_p_freq,[fmax+0.1])),rvec-ic.range_shift*1.5, dB,vmin=-3,vmax=ic.max_plot_dB)
    plt.title("%s %s\nnoise_floor=%1.2f (dB) peak SNR=%1.2f"%(ic.instrument_name,
                                                              stuffr.unix2datestr(t0),
                                                              noise_floor_0,
                                                              max_dB))
    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Virtual range (km)")
    plt.colorbar()
    plt.ylim([-10,ic.max_plot_range])
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


    ofname="%s/raw-%s.h5"%(dname,datestr)
    if ic.save_raw_voltage:
        save_raw_data(ofname,
                      t0,
                      z_all,
                      ic.s.freqs,
                      ic.station_id,
                      sr=ic.sample_rate/ic.dec,
                      freq_dur=ic.s.freq_dur)


    iono_ofname="%s/ionogram-%s.h5"%(dname,datestr)
    print("Saving ionogram %s"%(iono_ofname))
    ho=h5py.File(iono_ofname,"w")
    ho["I"]=IS
    ho["I_rvec"]=rvec
    ho["t0"]=t0
    ho["lat"]=ic.lat
    ho["lon"]=ic.lon
    ho["I_fvec"]=sfreqs
    ho["ionogram_version"]=1
    ho.close()

    delete_old_files(t0)

if __name__ == "__main__":

    ic=iono_config.get_config(write_waveforms=False)
    print("Starting analysis %f"%(time.time()))
    analyze_latest_sweep(ic)
