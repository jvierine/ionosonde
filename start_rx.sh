#!/bin/bash

source config.sh

while true;
do
    python3 rx_uhd.py --config=$IONO_CONFIG
    sleep 10
done

