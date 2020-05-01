import numpy as n
import time
import uhd
import stuffr

def check_lock(u,log=None,exit_if_not_locked=False):
    locked=u.get_mboard_sensor("gps_locked").to_bool()
    f=open("gps.log","a")
    f.write("%s lock=%d\n"%(stuffr.unix2datestr(time.time()),locked))
    f.close()
    if locked==False:
        if log!=None:
            log.log("Warning, GPS not locked")
        if exit_if_not_locked:
            print("No GPS lock. Exiting.")
            exit(0)
    return(locked)

def sync_clock(u,log):
    # synchronize the usrp clock to the pc clock
    # assume that the pc clock is synchronized using ntp
    gps_locked=check_lock(u)
    while gps_locked==False:
        print("Waiting for GPS lock. Check GPS antenna")
        time.sleep(10)
        gps_locked=check_lock(u)
        
    u.set_clock_source("gpsdo")        
    u.set_time_source("gpsdo")

    lastt=u.get_time_last_pps()
    nextt=u.get_time_last_pps()
    while nextt==lastt:
        time.sleep(0.05)
        lastt=nextt
        nextt=u.get_time_last_pps()
    time.sleep(0.2)
    u.set_time_next_pps(uhd.libpyuhd.types.time_spec(u.get_mboard_sensor("gps_time").to_int()+1))

    log.log(str(u.get_mboard_sensor("gps_gpgga")))
    log.log(str(u.get_mboard_sensor("gps_gprmc")))

    time.sleep(2.0)
    
    t_now=time.time()
    t_usrp=(u.get_time_now().get_full_secs()+u.get_time_now().get_frac_secs())
    t_gpsdo=u.get_mboard_sensor("gps_time")
    # these should be similar
    print("pc clock %1.2f usrp clock %1.2f gpsdo %1.2f"%(t_now,t_usrp,t_gpsdo.to_int()))
