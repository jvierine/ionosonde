#!/usr/bin/env python3
import glob
import re
import os
import iono_config
import numpy as np
import time

def delete_old_files(t0,data_path="/dev/shm"):
    """
    Deleting files older than two cycles ago
    """
    # delete older files
    fl=glob.glob("%s/raw*.bin"%(data_path))
    fl.sort()
    for f in fl:
        try:
            tfile=int(re.search(".*/raw-(.*)-....bin",f).group(1))
            if tfile < t0:
                os.system("rm %s"%(f))
        except:
            print("Error deleting file %s"%(f))



if __name__ == "__main__":
    s=iono_config.s
    while True:
        print("deleting")
        # figure out when to start the cycle. 
        t0=np.uint64(np.floor(time.time()/(s.sweep_len_s))*s.sweep_len_s)-5*s.sweep_len_s
        delete_old_files(t0,data_path=iono_config.data_path)
        time.sleep(s.sweep_len_s)

