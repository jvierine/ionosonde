#!/bin/bash

source config.sh

# remove cache
rm -f waveforms/cache*.h5

while true;
do
    python3 analyze_ionograms.py $IONO_CONFIG
    sleep 10
#    python3 overview_plots.py $IONO_CONFIG
done
    
