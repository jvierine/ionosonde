#!/bin/bash
export IONO_CONFIG="./config/irf_prn.ini"
export PYTHONPATH="/usr/local/lib/python3/dist-packages/"
sudo sysctl -w net.core.rmem_max=500000000
sudo sysctl -w net.core.wmem_max=2500000

