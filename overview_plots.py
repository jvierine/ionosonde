import numpy as n
import glob
import matplotlib.pyplot as plt
import h5py

import reanalyze_ionogram as rean
import stuffr


def overview_plots(t0,t1,max_r=800.0,min_r=50):
    fl=glob.glob("results/*/*.h5")
    fl.sort()
    
    t=[]
    v1f=[]
    dtt=[]
        
    for f in fl:
        try:
            h=h5py.File(f,"r")
            if "version" in h.keys() and h["version"].value == 1:
                if (h["t0"].value > t0) and (h["t0"].value < t1):
                    print(h["t0"].value)
                    print(stuffr.unix2datestr(t0))
                    print(stuffr.unix2datestr(t1))
                    print(stuffr.unix2datestr(h["t0"].value))
                    t.append(n.copy(h["t0"].value))
                    v1f.append(f)
            h.close()
        except:
            print("bad file %s"%(f))
    print(len(v1f))

    I,rvec,freq=rean.analyze_ionogram(fname=v1f[0],use_old=True)
    
    ridx=n.where(rvec < max_r)[0]
    ridx2=n.where( (rvec < max_r) & (rvec > min_r))[0]
    n_t=len(v1f)
    n_r=len(ridx)
    n_f=freq.shape[0]
    OR=n.zeros([n_t,n_r])
    OF=n.zeros([n_t,n_f])

    t=n.array(t)
    idx=n.argsort(t)
#    t=n.sort(t)
    for fi,f in enumerate(idx):
        f=v1f[idx[fi]]
        print(f)
        I,rvec,freq=rean.analyze_ionogram(fname=f,use_old=True)
        dtt.append(stuffr.unix2date(t[idx[fi]]))
        
#        plt.pcolormesh(I)
 #       plt.show()
  #      print(I.shape)
        OR[fi,:]=n.max(I[:,ridx],axis=0)
        OF[fi,:]=n.max(I[:,ridx2],axis=1)
        
    dBOR=10.0*n.log10(OR)
    dBOF=10.0*n.log10(OF)
    dBOF[n.isinf(dBOF)]=n.nan
    dBOR=dBOR-n.nanmedian(dBOR)
    dBOF=dBOF-n.nanmedian(dBOF)
    dBOF[n.isnan(dBOF)]=-3
    t=n.array(t)
    plt.pcolormesh(dtt,rvec[ridx],n.transpose(dBOR),vmin=-3,vmax=20)
    plt.show()
    plt.pcolormesh(dtt,0.5*(freq[:,0]+freq[:,1]),n.transpose(dBOF),vmin=-3,vmax=20)
    plt.show()

        

    
if __name__ == "__main__":
    overview_plots(t0=stuffr.date2unix(2020,5,22,0,0,0),
                   t1=stuffr.date2unix(2020,5,26,0,0,0))


