#!/bin/bash

source config.sh

WAIT=10
while true;
do
    python3 rx_uhd.py --config=$IONO_CONFIG
    echo "Waiting $WAIT seconds"
    sleep $WAIT
done

