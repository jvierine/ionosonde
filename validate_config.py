#!/usr/bin/env python3


import iono_config



if __name__ == "__main__":
    c=iono_config.get_config(write_waveforms=False)
    print(c)
    print("Configuration file is good")
