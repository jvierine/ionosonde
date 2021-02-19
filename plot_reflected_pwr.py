#!/usr/bin/env python3


import numpy as n
import matplotlib.pyplot as plt
import os
import re

f=os.popen("grep refl tx-current.log|tail -60")
#f=os.popen("grep refl tx-current.log")
fs=[]
ps=[]
pm=[]
for l in f.readlines():
    print(l.strip())
    f0=float(re.search(".* reflected pwr (.*) \(MHz\) (.*) \(dBm\).*",l).group(1))
    p=float(re.search(".* reflected pwr (.*) \(MHz\) (.*) \(dBm\).*",l).group(2))
    fs.append(f0)
    # 15 for coupling loss, 20 + 15 for attenuators
    ps.append(p+15+20+15)
    pm.append(p)

plt.figure(figsize=(8,4))
plt.subplot(121)
fs=n.array(fs)
plt.plot(fs/1e6,ps,".",label="True")
#plt.plot(fs,pm,".",label="Input")
#plt.legend()
plt.xlabel("Frequency (MHz)")
plt.ylabel("Reflected power (dBm)")
#plt.show()

plt.subplot(122)

p_tx=0.5
ps=n.array(ps)
p_ref=10**(ps/10.0)*1e-3
plt.plot(fs/1e6,(1.0+n.sqrt(p_ref/p_tx))/(1.0-n.sqrt(p_ref/p_tx)) ,".",label="True")
#plt.plot(fs,pm,".",label="Input")
#plt.legend()
plt.xlabel("Frequency (MHz)")
plt.ylabel("Standing wave ratio (SWR)")
plt.tight_layout()
plt.show()
