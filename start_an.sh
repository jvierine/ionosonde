#!/usr/bin/bash

while true;
do
    python analyze_ionograms.py
    python overview_plots.py
    sleep 60
done
    
