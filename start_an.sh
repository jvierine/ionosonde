#!/bin/bash

source config.sh

# remove old raw files
rm /dev/shm/raw*.bin

# remove cache
rm -f waveforms/cache*.h5

# Get values from current iono_config
. <(grep "^frequency_duration" $IONO_CONFIG | tr -d [:space:])
NFREQS=$(python3 iono_config.py $IONO_CONFIG |grep -c "^t=")

# Length of a sweep over all frequencies
SWEEP_LEN=$((frequency_duration * NFREQS))
# add 5 sec for finnish saving files
EXTRA=5

# remove cache
rm -f waveforms/cache*.h5

while true;
do
    python3 analyze_ionograms.py $IONO_CONFIG
#     python3 overview_plots.py $IONO_CONFIG

    # current time in seconds
    S=$(date -u +%s)

    # calculate number of seconds to wait until next sweep
    WAIT=$(((SWEEP_LEN+EXTRA) - (S % SWEEP_LEN)))
    echo "Waiting $WAIT seconds"
    date -d @$((S+WAIT))
    sleep $WAIT
done
