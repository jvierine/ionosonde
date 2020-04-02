def check_lock(u):
    return(u.get_mboard_sensor("gps_locked").to_bool())

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
    
#    t0=time.time()
 #   while (np.ceil(t0)-t0) < 0.2:
  #      t0=time.time()
   #     time.sleep(0.1)
        
   #    u.set_time_next_pps(uhd.libpyuhd.types.time_spec(np.ceil(t0)))
    time.sleep(0.2)
    t_now=time.time()
    t_usrp=(u.get_time_now().get_full_secs()+u.get_time_now().get_frac_secs())
    t_gpsdo=u.get_mboard_sensor("gps_time")
    # these should be similar
    print("pc clock %1.2f usrp clock %1.2f gpsdo %1.2f"%(t_now,t_usrp,t_gpsdo.to_int()))
