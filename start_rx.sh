#!/usr/bin/bash

export PYTHONPATH="/usr/local/lib/python3/dist-packages/"
sudo sysctl -w net.core.rmem_max=500000000
sudo sysctl -w net.core.wmem_max=2500000
while true;
do
    python3 rx_uhd_test.py
    sleep 10
done
    
