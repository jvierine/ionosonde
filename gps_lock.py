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

def sync_clock(u,log, min_sync_time=300.0):
    # Based on the specs for the gpsdo, it takes 5 minutes to warm 
    # up after restart
    t0=time.time()
        
    not_locked_for_long_enough=True
    if min_sync_time < 10:
        min_sync_time=20.0
    
    while not_locked_for_long_enough:
        time_locked=time.time()-t0
        
        if time_locked > min_sync_time:
            # we've been locked for long enough. start the receiver.
            not_locked_for_long_enough=False
        
        print("Waiting for GPS lock.\nObtained lock for %1.0f/%1.0f seconds\nCheck GPS antenna if no lock obtained in 60 seconds."%(time_locked,min_sync_time))
        time.sleep(10)
        # check for lock. don't log or exit 
        gps_locked=check_lock(u)
        
        if gps_locked == False:
            # reset t0 if not locked
            t0=time.time()
            
        
        
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


if __name__ == "__main__":
    u = uhd.usrp.MultiUSRP()
    locked=check_lock(u,log=None,exit_if_not_locked=False)
    print("GPS locked %d"%(locked))
