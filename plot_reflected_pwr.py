#!/usr/bin/env python


import numpy as n
import matplotlib.pyplot as plt
import os
import re

f=os.popen("grep refl tx-current.log|tail -60")
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

plt.plot(fs,ps,".",label="True")
plt.plot(fs,pm,".",label="Input")
plt.legend()
plt.xlabel("Frequency (MHz)")
plt.ylabel("Reflected power (dBm)")
plt.show()
