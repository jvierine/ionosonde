ALL:
	g++ -o rx_uhd rx_uhd.cpp -luhd -lboost_program_options -lboost_system -lboost_thread -lboost_date_time -lboost_regex -lboost_serialization
