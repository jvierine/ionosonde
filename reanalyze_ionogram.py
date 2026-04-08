#!/usr/bin/env python3
import argparse
import numpy as np
import h5py
import matplotlib.pyplot as plt
import scipy.constants as const
import os

import create_waveform
import stuffr
import iono_config


def incoh_an(z, code, nr=500):
    code_len=len(code)
    S=np.zeros([nr, code_len])
#    C=np.conj(np.fft.fft(code))
    for ci in range(z.shape[0]):
        for ri in range(nr):
            tidx=np.array(np.mod(np.arange(code_len)+ri, code_len), dtype=np.int)
            S[ri, :]+=np.fft.fftshift(np.abs(np.fft.fft(z[ci, tidx]*np.conj(code)))**2.0)
#    for fi in range(code_len):
#        S[:,fi]=S[:,fi]-np.median(S[:,fi])
    return(S)


def analyze_ionogram(ic,
                     fname,
                     avg_spec=False,
                     plot_ionogram=False,
                     plot_spectra=False,
                     use_old=False,
                     max_range=1000,
                     min_range=0,
                     version=1):

    with h5py.File(fname, "r") as h:

        t0=h["t0"].value
        hdname=stuffr.unix2iso8601_dirname(h["t0"].value, ic)
        dname="%s/%s" % (ic.ionogram_path, hdname)
        os.system("mkdir -p %s" % (dname))
        datestr=stuffr.unix2iso8601(t0)
        iono_ofname="%s/ionogram-%s.h5" % (dname, datestr)
        print("looking for %s" % (iono_ofname))
        if use_old:
            if os.path.exists(iono_ofname):
                with h5py.File(iono_ofname, "r") as hi:
                    I=np.copy(hi["I"].value)
                    r=np.copy(hi["I_rvec"].value)
                    f=np.copy(hi["I_fvec"].value)
                return(I, r, f)

        if "version" not in h.keys():
            print("Not correction file version")
            return

        if h["version"].value != version:
            print("Not correct file version")
            return

#        if use_old:
#            if "I" in h.keys():
#                I=np.copy(h["I"].value)
#                I_fvec=np.copy(h["I_fvec"].value)
#                I_rvec=np.copy(h["I_rvec"].value)
#                h.close()
#                return(I,I_rvec,I_fvec)

        # float16 re and im to complex64
        z_all=np.array(h["z_re"].value+h["z_im"].value*1j, dtype=np.complex64)
        freqs=h["freqs"].value
        codes=h["codes"].value
        code_type=h["code_type"].value
        if "code_len" in h.keys():
            code_len=h["code_len"].value
        else:
            code_len=10000
    #    print(codes)
        sample_rate=h["sample_rate"].value
        dr=const.c/h["sample_rate"].value/2.0/1e3
        t0=h["t0"].value
        n_freqs=freqs.shape[0]
        if "station_id" in h.keys():
            station_id=h["station_id"].value
        else:
            station_id=0

        iono_freqs=0.5*(freqs[:, 0]+freqs[:, 1])
        fmax=np.max(iono_freqs)
        n_plot_freqs=int((fmax+0.5)/0.1)+1
        iono_p_freq=np.linspace(0, fmax+0.5, num=n_plot_freqs)
        I=np.zeros([n_plot_freqs, code_len], dtype=np.float32)

        wf=create_waveform.create_prn_dft_code(clen=code_len, seed=station_id)
        WF=np.fft.fft(wf)
        rvec=np.arange(code_len)*dr

        IS=np.zeros([n_freqs, code_len])

        for i in range(n_freqs):
            z=np.copy(z_all[i, :])
            z=z-np.mean(z)

            N_codes=len(z)/code_len
            z.shape=(N_codes, code_len)

            echoes=np.zeros([N_codes, code_len], dtype=np.complex64)
            spec=np.zeros([N_codes, code_len], dtype=np.float)

            for ci in range(N_codes):
                echoes[ci, :]=np.fft.ifft(np.fft.fft(z[ci, :])/WF)

            # remove edge effect when hopping in frequency
            echoes[N_codes-1, :]=echoes[N_codes-2, :]

            for ri in range(code_len):
                spec[:, ri]=np.fft.fftshift(np.abs(np.fft.fft(echoes[:, ri]))**2.0)
            for fi in range(N_codes):
                spec[fi, :]=spec[fi, :]/np.median(np.abs(spec[fi, :]))

            if avg_spec:
                sw=np.fft.fft(np.repeat(1.0/4, 4), N_codes)
                for ri in range(code_len):
                    spec[:, ri]=np.roll(np.real(np.fft.ifft(np.fft.fft(spec[:, ri])*sw)), -2)
            pif=int(iono_freqs[i]/0.1)
            I[pif, :]+=np.max(spec, axis=0)
            IS[i, :]=np.max(spec, axis=0)

            if plot_spectra:
                tv=np.arange(N_codes)
                dBP=np.transpose(10.0*np.log10(np.abs(echoes)**2.0))
                nf=np.nanmedian(dBP)
                plt.pcolormesh(tv, rvec, dBP, vmin=nf, vmax=nf+20)
                plt.ylim([0, 800])
                plt.colorbar()
                plt.show()
                dBS=np.transpose(10.0*np.log10(spec))
                nf=np.nanmedian(dBS)
                dop=3e8*np.fft.fftshift(
                    np.fft.fftfreq(N_codes, d=code_len/float(sample_rate)))/2.0/(freqs[i, 0]*1e6)
                plt.pcolormesh(dop, rvec, dBS, vmin=nf, vmax=nf+20)
                plt.xlabel("Doppler shift (m/s)")
                plt.ylabel("Range (km)")
                plt.ylim([0, 800])
                plt.colorbar()
                plt.show()

        if plot_ionogram:
            dBI=np.transpose(10.0*np.log10(I))
            dBI[np.isinf(dBI)]=np.nan
            noise_floor=np.nanmedian(dBI)
            dBI=dBI-noise_floor
            dBI[np.isnan(dBI)]=-3
            plt.pcolormesh(np.concatenate((iono_p_freq, [fmax+0.1])), rvec, dBI, vmin=-3, vmax=20.0)
            plt.title("%s %s\nNoise floor=%1.2f (dB)" % (ic.instrument_name,
                                                         stuffr.unix2datestr(h["t0"].value),
                                                         noise_floor))

            plt.xlim([np.min(iono_freqs)-0.5, np.max(iono_freqs)+0.5])
            #    plt.pcolormesh(freqs[:,0],rvec,dBI,vmin=0,vmax=20)
            plt.ylim([0, 800])
            plt.colorbar()
            plt.xlabel("Frequency (MHz)")
            plt.ylabel("Virtual range (km)")
            plt.tight_layout()
            ofname="%s/%s.png" % (dname, datestr)
            print("Saving ionogram %s" % (ofname))
            plt.savefig(ofname)
            plt.clf()
            plt.close()

        print("Saving ionogram %s" % (iono_ofname))

        with h5py.File(iono_ofname, "w") as ho:
            ho["I"]=IS
            ho["I_rvec"]=rvec
            ho["t0"]=h["t0"].value
            ho["lat"]=h["lat"].value
            ho["lon"]=h["lon"].value
            ho["I_fvec"]=freqs
            ho["ionogram_version"]=1

    return(IS, rvec, freqs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'filename',
        help='''File to reanalyze.'''
    )
    parser.add_argument(
        '-c', '--config',
        default="config/default.ini",
        help='''Configuration file. (default: %(default)s)''',
    )
    parser.add_argument(
        '-w', '--create_waveforms',
        default=False,
        action="store_true",
        help='''Create waveform files. (default: %(default)s)''',
    )
    parser.add_argument(
        '-v', '--verbose',
        action="store_true",
        help='''Increase output verbosity. (default: %(default)s)''',
    )
    op = parser.parse_args()

    ic = iono_config.get_config(
        config=op.config,
        write_waveforms=op.create_waveforms,
        quiet=not op.verbose
    )
    I, rvec, freq = analyze_ionogram(
        ic,
        op.filename,
        avg_spec=False,
        plot_ionogram=False,
        plot_spectra=False,
        version=1
    )
