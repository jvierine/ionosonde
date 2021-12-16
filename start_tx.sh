#!/bin/bash

source config.sh

echo "Removing cached deconvolution matrices"
rm waveforms/cache*.h5
WAIT=10
while true;
do
    python3 tx_uhd.py --config=$IONO_CONFIG
    echo "Waiting $WAIT seconds"
    sleep $WAIT
done
