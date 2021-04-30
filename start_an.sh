#!/bin/bash

source config.sh

# remove old raw files
# todo: read directory from config file.
# maybe this is best done at startup of rx_uhd.py
unset -v latest
for file in /dev/shm/raw*.bin; do
  [[ $file -nt $latest ]] && latest=$file
done

# remove raw-files if config been updated
[[ $IONO_CONFIG -nt $latest ]] && rm /dev/shm/raw*.bin

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

PROGRESS_BAR_WIDTH=50  # progress bar length in characters

draw_progress_bar() {
  # Arguments: current value, max value, unit of measurement (optional)
  local __value=$1
  local __max=$2
  local __unit=${3:-""}  # if unit is not supplied, do not display it

  # Calculate percentage
  if (( $__max < 1 )); then __max=1; fi  # anti zero division protection
  local __percentage=$(( 100 - ($__max*100 - $__value*100) / $__max ))

  # Rescale the bar according to the progress bar width
  local __num_bar=$(( $__percentage * $PROGRESS_BAR_WIDTH / 100 ))

  # Draw progress bar
  printf "["
  for b in $(seq 1 $__num_bar); do printf "#"; done
  for s in $(seq 1 $(( $PROGRESS_BAR_WIDTH - $__num_bar ))); do printf " "; done
  printf "] $__percentage%% ($__value / $__max $__unit)\r"
}

wait_until() {
    target=$1
    now=$(date -u +%s)
    total_wait=$((target - now))
    while true; do
        # Get current value of uploaded bytes
        now=$(date -u +%s)
        remain_wait=$((target - now))

        # Draw a progress bar
        draw_progress_bar $remain_wait $total_wait "seconds"

        # Check if we reached 100%
        if [ $remain_wait -le 0 ]; then break; fi
        sleep 1  # Wait before redrawing
    done
    # Go to the newline at the end
    printf "\n"
}

while true;
do
    python3 analyze_ionograms.py --config=$IONO_CONFIG
#     python3 overview_plots.py $IONO_CONFIG

    # current time in seconds
    S=$(date -u +%s)
    date -d @$S +"Now: %F %T %Z"

    # calculate number of seconds to wait until next sweep
    WAIT=$(((SWEEP_LEN+EXTRA) - (S % SWEEP_LEN)))
    date -d @$((S+WAIT)) +"Waiting ${WAIT}s until %F %T %Z for current sweep to end"
    wait_until $((S+WAIT))
done
