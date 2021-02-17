#!/usr/bin/bash

source config.sh

# remove cache
rm -f waveforms/cache*.h5

while true;
do
    python analyze_ionograms.py $IONO_CONFIG
    sleep 10
#    python overview_plots.py $IONO_CONFIG
done
    
