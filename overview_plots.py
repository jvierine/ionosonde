#!/usr/bin/env python3
import numpy as n
import glob
import matplotlib.pyplot as plt
import h5py
import time

import reanalyze_ionogram as rean
import stuffr
import iono_config

def overview_plots(t0,t1,max_r=500,gc=20):
    fl=glob.glob("results/*/ionogram*.h5")
    fl.sort()

    t=[]
    v1f=[]
    dtt=[]


    for f in fl:
        try:
            h=h5py.File(f,"r")
            if "ionogram_version" in h.keys() and h["ionogram_version"].value == 1:
                if (h["t0"].value > t0) and (h["t0"].value < t1):
#                    print("t0 %d t1 %d t %d"%(t0,t1,h["t0"].value))
 #                   print(h["t0"].value)
                    t.append(n.copy(h["t0"].value))
                    v1f.append(f)
            h.close()
        except Exception as e:
            print("bad file %s"%(f))
    #   print(len(v1f))
    if len(v1f)== 0:
        print("no data")
        return

    h=h5py.File(v1f[0],"r")
    n_f=len(h["I_fvec"].value)
    freq=n.copy(h["I_fvec"].value)
    h.close()

    n_t=len(v1f)
    n_r=max_r
    OR=n.zeros([n_t,n_r])
    OF=n.zeros([n_t,n_f])

    t=n.array(t)
    idx=n.argsort(t)
    rvec=n.arange(n_r)*1.5
    for fi,f in enumerate(idx):
        f=v1f[idx[fi]]
        print(f)
        h=h5py.File(f,"r")
        I=n.copy(h["I"].value)
        dtt.append(stuffr.unix2date(t[idx[fi]]))
        for freq_i in range(I.shape[0]):
            I[freq_i,:]=I[freq_i,:]/n.median(n.abs(I[freq_i,:]))
#        plt.pcolormesh(I)
 #       plt.colorbar()
  #      plt.show()
#        plt.pcolormesh(I)
 #       plt.show()
  #      print(I.shape)
        OR[fi,:]=n.max(I[:,0:max_r],axis=0)
        OF[fi,:]=n.max(I[:,gc:max_r],axis=1)
        h.close()

    dBOR=10.0*n.log10(OR)
    dBOF=10.0*n.log10(OF)
    dBOF[n.isinf(dBOF)]=n.nan
    dBOR=dBOR-n.nanmedian(dBOR)
    dBOF=dBOF-n.nanmedian(dBOF)
    dBOF[n.isnan(dBOF)]=-3
    t=n.array(t)
    plt.figure(figsize=(1.5*8,1.5*6))
    # 30 km range shift
    plt.pcolormesh(dtt,rvec-iono_config.range_shift*1.5,n.transpose(dBOR),vmin=0,vmax=10)
    plt.colorbar()
    plt.xlabel("Time (UTC)")
    plt.ylabel("Virtual range (km)")
    plt.tight_layout()
    print("saving overview_rt.png")
    plt.savefig("overview_rt.png")
    plt.close()
    plt.clf()
#    plt.show()

    plt.figure(figsize=(1.5*8,1.5*6))
    plt.pcolormesh(dtt,0.5*(freq[:,0]+freq[:,1]),n.transpose(dBOF),vmin=0,vmax=10)
    plt.colorbar()
    plt.xlabel("Time (UTC)")
    plt.ylabel("Frequency (MHz)")

    plt.tight_layout()
    print("saving overview_ft.png")
    plt.savefig("overview_ft.png")
    plt.close()
    plt.clf()
#    plt.show()




if __name__ == "__main__":
    #stuffr.date2unix(2020,5,25,0,0,0)
    #stuffr.date2unix(2020,5,27,0,0,0)
    tnow=time.time()
    overview_plots(t0=tnow-48*3600,
                   t1=tnow)


