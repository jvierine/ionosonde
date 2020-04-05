//
// Copyright 2010-2011 Ettus Research LLC
// Copyright 2018 Ettus Research, a National Instruments Company
//
// SPDX-License-Identifier: GPL-3.0-or-later
//

#include <uhd/usrp/multi_usrp.hpp>
#include <uhd/utils/safe_main.hpp>
#include <uhd/utils/thread.hpp>
#include <boost/algorithm/string.hpp>
#include <boost/format.hpp>
#include <boost/program_options.hpp>
#include <complex>
#include <iostream>
#include <unistd.h>

namespace po = boost::program_options;

int UHD_SAFE_MAIN(int argc, char* argv[])
{
    // variables to be set by po
    std::string args;
    std::string wire;
    double seconds_in_future;
    size_t total_num_samps;
    double rate;
    std::string channel_list;

    // setup the program options
    po::options_description desc("Allowed options");
    // clang-format off
    desc.add_options()
        ("help", "help message")
        ("args", po::value<std::string>(&args)->default_value(""), "single uhd device address args")
        ("wire", po::value<std::string>(&wire)->default_value(""), "the over the wire type, sc16, sc8, etc")
        ("secs", po::value<double>(&seconds_in_future)->default_value(1.5), "number of seconds in the future to receive")
        ("nsamps", po::value<size_t>(&total_num_samps)->default_value(10000), "total number of samples to receive")
        ("rate", po::value<double>(&rate)->default_value(1e6), "rate of incoming samples")
        ("dilv", "specify to disable inner-loop verbose")
        ("channels", po::value<std::string>(&channel_list)->default_value("0"), "which channel(s) to use (specify \"0\", \"1\", \"0,1\", etc)")
    ;
    // clang-format on
    po::variables_map vm;
    po::store(po::parse_command_line(argc, argv, desc), vm);
    po::notify(vm);

    bool verbose = vm.count("dilv") == 0;

    // create device
    uhd::usrp::multi_usrp::sptr usrp = uhd::usrp::multi_usrp::make(args);

    // detect which channels to use
    std::vector<std::string> channel_strings;
    std::vector<size_t> channel_nums;
    boost::split(channel_strings, channel_list, boost::is_any_of("\"',"));
    for (size_t ch = 0; ch < channel_strings.size(); ch++) {
        size_t chan = std::stoi(channel_strings[ch]);
        if (chan >= usrp->get_tx_num_channels() or chan >= usrp->get_rx_num_channels()) {
            throw std::runtime_error("Invalid channel(s) specified.");
        } else
            channel_nums.push_back(std::stoi(channel_strings[ch]));
    }
    
    // use internal gpsdo
    usrp->set_clock_source("gpsdo");
    usrp->set_time_source("gpsdo");

    // Wait for GPS lock
    bool gps_locked = usrp->get_mboard_sensor("gps_locked").to_bool();
    while (gps_locked == false){
      // sleep for 10 seconds
      std::this_thread::sleep_for(std::chrono::seconds(10));
      gps_locked = usrp->get_mboard_sensor("gps_locked").to_bool();
      printf("No GPS lock, waiting for lock.\n");
    }
    
    // Set to GPS time
    uhd::time_spec_t gps_time = uhd::time_spec_t(int64_t(usrp->get_mboard_sensor("gps_time").to_int()));
    usrp->set_time_next_pps(gps_time + 1.0);

    // Wait for it to apply
    // The wait is 2 seconds because N-Series has a known issue where
    // the time at the last PPS does not properly update at the PPS edge
    // when the time is actually set.
    std::this_thread::sleep_for(std::chrono::seconds(2));

    // Check times
    gps_time = uhd::time_spec_t(int64_t(usrp->get_mboard_sensor("gps_time").to_int()));
				
    uhd::time_spec_t time_last_pps = usrp->get_time_last_pps();
    printf("USRP time %1.4f GPSDO time %1.4f\n",time_last_pps.get_real_secs(),gps_time.get_real_secs());
    
    // set the rx sample rate
    printf("Setting sample-rate to %1.2f",rate);
    usrp->set_rx_rate(rate);
    
    // create a receive streamer
    uhd::stream_args_t stream_args("fc32", wire); // complex floats
    stream_args.channels             = channel_nums;
    uhd::rx_streamer::sptr rx_stream = usrp->get_rx_stream(stream_args);

    // setup streaming
    double tstart=time_last_pps.get_real_secs()+5.0;
    uhd::time_spec_t ts_t0=uhd::time_spec_t(tstart);
    printf("Streaming start at %f\n",time_last_pps.get_real_secs()+5.0);
    uhd::stream_cmd_t stream_cmd(uhd::stream_cmd_t::STREAM_MODE_START_CONTINUOUS);
    // stream_cmd.num_samps  = total_num_samps;
    stream_cmd.stream_now = false;
    stream_cmd.time_spec  = ts_t0;
    
    rx_stream->issue_stream_cmd(stream_cmd);

    // metadata
    uhd::rx_metadata_t md;

    // allocate buffer to receive with samples
    std::vector<std::complex<float>> buff(rx_stream->get_max_num_samps());
    std::vector<void*> buffs;
    for (size_t ch = 0; ch < rx_stream->get_num_channels(); ch++)
        buffs.push_back(&buff.front()); // same buffer for each channel

    // the first call to recv() will block this many seconds before receiving
    double timeout = 7.0 + 0.1; // timeout (delay before receive + padding)

    size_t num_acc_samps = 0; // number of accumulated samples
    while (1)
    {
      // receive a single packet
      size_t num_rx_samps = rx_stream->recv(buffs, buff.size(), md, timeout, true);
      
      // use a small timeout for subsequent packets
      timeout = 0.1;
      
      // handle the error code
      if (md.error_code == uhd::rx_metadata_t::ERROR_CODE_TIMEOUT)
	break;
      if (md.error_code != uhd::rx_metadata_t::ERROR_CODE_NONE) {
	throw std::runtime_error(str(boost::format("Receiver error %s") % md.strerror()));
      }
      // check md.time_stamp
      // if we are at the boundary of a cycle, change frequency
    }
    
 
    return EXIT_SUCCESS;
}
