#!/bin/bash
export IONO_CONFIG="./config/unis_lyr.ini"
export IONO_CONFIG_OBLIQUE="./config/irf_prn3_uppsala_lycksele.ini"
export PYTHONPATH="/usr/local/lib/python3/dist-packages/"

# to get the following to work as a non-root user add:
#
# ionosonde_user ALL = NOPASSWD: /sbin/sysctl -w net.core.?mem_max*
#
# to /etc/sudoers.d/ionosonde_user or /etc/sudoers
#
sudo sysctl -w net.core.rmem_max=500000000
sudo sysctl -w net.core.wmem_max=2500000

