#!/usr/bin/env python3
import argparse
import matplotlib

import numpy as np
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
import scipy.constants as const
from datetime import datetime, timedelta


matplotlib.use("Agg")


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
    z_re=np.array(np.real(z_all), dtype=np.float16)
    z_im=np.array(np.imag(z_all), dtype=np.float16)
    print("saving raw complex voltage %s" % (fname))
    with h5py.File(fname, "w") as ho:
        ho["z_re"]=z_re
        ho["t0"]=t0
        ho["z_im"]=z_im
        ho["freqs"]=freqs
        ho["freq_dur"]=freq_dur
        ho["sample_rate"]=sr
        ho["station_id"]=station


def delete_old_files(t0, data_path="/dev/shm"):
    """
    Deleting files that are from the currently analyzed sweep or older.
    """
    # delete older files
    fl=glob.glob("%s/raw*.bin" % (data_path))
    fl.sort()
    for f in fl:
        try:
            tfile=int(re.search(".*/raw-(.*)-....bin", f).group(1))
            if tfile <= t0:
                os.system("rm %s" % (f))
        except Exception as e:
            print("error deleting file")


def analyze_latest_sweep(ic, data_path="/dev/shm"):
    """
    Analyze an ionogram, make some plots, save some data
    """
    # TODO: save raw voltage to file,
    # then analyze raw voltage file with common program
    # figure out what cycle is ready
    s=ic.s
    n_rg=ic.n_range_gates
    t0=np.uint64(np.floor(time.time()/(s.sweep_len_s))*ic.s.sweep_len_s-ic.s.sweep_len_s)

    sfreqs=np.array(ic.s.freqs)
    iono_freqs=sfreqs[:, 0]
    fmax=np.max(iono_freqs)
    #
    plot_df=0.1

    n_plot_freqs=int((fmax+0.5)/plot_df)
    iono_p_freq=np.arange(n_plot_freqs)*plot_df  # np.linspace(0,fmax+0.5,num=n_plot_freqs)
    I=np.zeros([n_plot_freqs, n_rg], dtype=np.float32)
    IS=np.zeros([sfreqs.shape[0], n_rg], dtype=np.float32)

    # number of transmit "pulses"
    n_t=int(ic.s.freq_dur*1000000/(ic.code_len*ic.dec))

    all_spec=np.zeros([ic.s.n_freqs, n_t, n_rg], dtype=np.float32)

    # IPP length
    dt=ic.dec*ic.code_len/1e6

    # range step
    dr = ic.dec*const.c/ic.sample_rate/2.0/1e3

    rvec=np.arange(float(n_rg))*dr
    p_rvec=np.arange(float(n_rg)+1)*dr
    fvec=np.fft.fftshift(np.fft.fftfreq(n_t, d=dt))

    hdname=stuffr.unix2iso8601_dirname(t0, ic)
    dname="%s/%s" % (ic.ionogram_path, hdname)
    os.system("mkdir -p %s" % (dname))

    print("Duration of each frequency: {}".format(ic.s.freq_dur))
    z_all=np.zeros([ic.s.n_freqs, int(ic.s.freq_dur*100000)], dtype=np.complex64)

    noise_floors=[]

    for i in range(ic.s.n_freqs):
        fname="%s/raw-%d-%03d.bin" % (data_path, t0, i)
        if os.path.exists(fname):
            z=np.fromfile(fname, dtype=np.complex64)
            z_all[i, :]=z
            N=len(z)
            code_idx=ic.s.code_idx(i)

            if ic.spectral_whitening:
                # reduce receiver noise due to narrow band
                # broadcast signals by trying to filter them out
                if ic.pulse_lengths[code_idx] > 0:
                    z = p.spectral_filter_pulse(z,
                                                ipp=ic.ipps[code_idx],
                                                pulse_len=ic.pulse_lengths[code_idx])

            res=p.analyze_prc2(z,
                               code=ic.orig_codes[code_idx],
                               cache_idx=code_idx+1000000*ic.station_id,
                               rfi_rem=False,
                               spec_rfi_rem=True,
                               n_ranges=n_rg)

            plt.figure(figsize=(1.5*8, 1.5*6))
            plt.rc('font', size=15)
            plt.rc('axes', titlesize=20)
            plt.subplot(121)

            tvec=np.arange(int(N/ic.code_len), dtype=np.float64)*dt
            p_tvec=np.arange(int(N/ic.code_len)+1, dtype=np.float64)*dt
            with np.errstate(divide='ignore'):
                dBr=10.0*np.log10(np.transpose(np.abs(res["res"])**2.0))
            noise_floor=np.nanmedian(dBr)
            noise_floor_0=noise_floor
            noise_floors.append(noise_floor_0)
            dBr=dBr-noise_floor
            dB_max=np.nanmax(dBr)
            plt.pcolormesh(p_tvec, p_rvec-ic.range_shift*dr, dBr, vmin=0, vmax=ic.max_plot_dB)
            plt.xlabel("Time (s)")
            plt.title("Range-Time Power f=%d (dB)\nnoise_floor=%1.2f (dB) peak SNR=%1.2f"
                      % (i, noise_floor, dB_max))
            plt.ylabel("Range (km)")
            plt.ylim([-10, ic.max_plot_range])

            plt.colorbar()
            plt.subplot(122)
#            S=np.abs(res["spec"])**2.0
            S=res["spec_snr"]

            #sw=np.fft.fft(np.repeat(1.0/4,4),S.shape[0])
            #for rg_id in range(S.shape[1]):
            #    S[:,rg_id]=np.roll(np.real(np.fft.ifft(np.fft.fft(S[:,rg_id])*sw)),-2)

            all_spec[i, :, :]=S
            # 100 kHz steps for ionogram freqs
            pif=np.argmin(np.abs(iono_freqs[i]-iono_p_freq))
#            pif=int(iono_freqs[i]/0.1)

            # collect peak SNR across all doppler frequencies
            I[pif, :]+=np.max(S, axis=0)
            IS[i, :]=np.max(S, axis=0)

            # SNR in dB scale
            with np.errstate(divide='ignore'):
                dBs=10.0*np.log10(np.transpose(S))
            noise_floor=np.nanmedian(dBs)
            max_dB=np.nanmax(dBs)
            plt.pcolormesh(fvec, rvec-ic.range_shift*dr, dBs, vmin=0, vmax=ic.max_plot_dB)
            plt.ylim([-10, ic.max_plot_range])

            plt.title("Range-Doppler Power (dB)\nnoise_floor=%1.2f (dB) peak SNR=%1.2f (dB)"
                      % (noise_floor, max_dB))
            plt.xlabel("Frequency (Hz)")
            plt.ylabel("Virtual range (km)")

            cb=plt.colorbar()
            cb.set_label("SNR (dB)")
            plt.tight_layout()

            plt.savefig("%s/iono-%03d.png" % (dname, i))
            plt.close()
            plt.clf()
        else:
            return(0)
            print("file %s not found" % (fname))

    i_fvec=np.zeros(ic.s.n_freqs)
    for fi in range(ic.s.n_freqs):
        i_fvec[fi]=s.freq(fi)
    with np.errstate(divide='ignore'):
        dB=10.0*np.log10(np.transpose(I))
    dB[np.isinf(dB)]=np.nan
    noise_floor=np.nanmedian(dB)

    for i in range(dB.shape[1]):
        dB[:, i]=dB[:, i]-np.nanmedian(dB[:, i])

    dB[np.isnan(dB)]=-3

    noise_floor_0=np.mean(np.array(noise_floors))

    plt.figure(figsize=(1.5*8, 1.5*6))
    max_dB=np.nanmax(dB)
    plt.pcolormesh(np.concatenate((iono_p_freq, [fmax+0.1])),
                   rvec-ic.range_shift*1.5, dB, vmin=0, vmax=ic.max_plot_dB)
    plt.title("%s %s UT\nnoise_floor=%1.2f (dB) peak SNR=%1.2f"
              % (ic.instrument_name, stuffr.unix2datestr(t0), noise_floor_0, max_dB))
    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Virtual range (km)")
    #plt.colorbar()
    cb=plt.colorbar()
    cb.set_label("SNR (dB)")

    plt.ylim([-10, ic.max_plot_range])
    plt.xlim([np.min(iono_freqs)-0.5, np.max(iono_freqs)+0.5])
    plt.tight_layout()

    datestr=stuffr.unix2iso8601(t0)
    ofname="%s/%s.png" % (dname, datestr.replace(':','.'))
    print("Saving ionogram %s" % (ofname))
    plt.savefig(ofname)
    plt.clf()
    plt.close()
    # make link to latest plot
    os.system("ln -sf %s latest.png" % (ofname))

    ofname="%s/raw-%s.h5" % (dname, datestr.replace(':','.'))
    if ic.save_raw_voltage:
        save_raw_data(ofname,
                      t0,
                      z_all,
                      ic.s.freqs,
                      ic.station_id,
                      sr=ic.sample_rate/ic.dec,
                      freq_dur=ic.s.freq_dur)

    iono_ofname="%s/ionogram-%s.h5" % (dname, datestr.replace(':','.'))
    print("Saving ionogram %s" % (iono_ofname))
    with h5py.File(iono_ofname, "w") as ho:
        ho["I"]=IS
        ho["I_rvec"]=rvec
        ho["t0"]=t0
        ho["lat"]=ic.lat
        ho["lon"]=ic.lon
        ho["I_fvec"]=sfreqs
        ho["ionogram_version"]=1

    # keep two sweeps in ringbuffer to allow oblique analysis to also finish
    delete_old_files(t0-ic.s.sweep_len_s*2)
    os.system("ln -sf %s/%s.png %s/latest.png" % (hdname, datestr.replace(':','.'), ic.ionogram_path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config',
        default="config/default.ini",
        help='''Configuration file. (default: %(default)s)''',
    )
    op = parser.parse_args()

    # don't create waveform files.
    ic = iono_config.get_config(config=op.config, write_waveforms=True)
    print("Starting analysis %s" % (datetime.fromtimestamp(time.time()).strftime("%FT%T")))
    analyze_latest_sweep(ic)
