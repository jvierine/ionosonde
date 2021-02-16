#!/usr/bin/bash

export PYTHONPATH=/usr/local/lib/python3/dist-packages
source config.sh
sudo sysctl -w net.core.wmem_max=250000000
sudo sysctl -w net.core.rmem_max=500000000
while true;
do
    python3 tx_uhd.py $IONO_CONFIG
    sleep 10
done
