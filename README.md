# Coded continuous-wave ionosonde 

A basic software defined radio ionosonde implementation written purely in Python. The ionosonde uses arbitrary transmit waveforms, which can be defined by the user. The default configuration uses pseudorandom phase coded continuous wave pulses. 

On receive, a range-Doppler spectrum of the received echoes is estimated and an ionogram is produced using the configured frequency sweep. 

## Dependencies

- Requires UHD Library 3.15. The UHD library needs to be compiled with the Python API enabled. 
- Numpy, Matplotlib, Scipy, Psutil

