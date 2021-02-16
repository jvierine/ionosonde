#!/usr/bin/bash

source config.sh

while true;
do
    python analyze_ionograms.py $IONO_CONFIG
    python overview_plots.py $IONO_CONFIG
done
    
