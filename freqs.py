#!/usr/bin/env python3
import matplotlib.pyplot as plt
import numpy as n
import scipy.signal as ss

# these are the frequency "gaps" we are allowed to transmit in
freqs=[[2.2,2.3],
       [2.35,2.45],
       [2.51,2.61],
       [2.65,2.75],
       [3.155,3.255],
       [3.3,3.4],
       [3.95,4.0],
       [4.438,4.538],
       [4.6,4.65],
       [4.85,4.95],
       [5.005,5.105],
       [5.155,5.255],
       [5.305,5.335],
       [5.4,5.45],
       [5.8,5.9],
       [5.95,6.05],
       [6.1,6.2],
       [6.8,6.85],
       [6.9,7],
       [7.2,7.3],
       [7.35,7.45],
       [7.5,7.6],
       [7.65,7.75],
       [8.095,8.195],
       [9.4,9.5],
       [11.6,11.7],
       [13.57,13.67],
       [15.1,15.2],
       [15.7,15.8],
       [17.48,17.58],
       [18.9,19.0],
       [21.45,21.55],
       [25.01,25.11]]

def simple_plot():

    for f in freqs:
        plt.fill_between([f[0],f[0],f[1],f[1]],[0,1,1,0])
    plt.title("Licensed frequency bands")
    plt.xlabel("Frequenc (MHz)")
    plt.show()

def get_spec(sample_rate=10e6,
             code_length_sec=0.1,
             plot=False,
             roll_off=20000.0):
    """
    Return a spectrum mask, based on the frequencies the ionosonde is allowed to
    transmit on. Uses the array freq, which is globally defined in this python module.

    sample_rate = what is the sample-rate of the signal to be generated
    code_length_sec = the length of the code in seconds
    roll_off = how fast the transition from pass band to stop band occurs (Hz)
    """
    # how long is the code in samples
    code_len=int(sample_rate*code_length_sec)
    # initialize a vector to hold the code
    code_spec=n.zeros(code_len,dtype=n.complex64)
    # frequencies of the spectral components
    code_freqs=n.fft.fftshift(n.fft.fftfreq(code_len,d=1.0/sample_rate))/1e6 + sample_rate/2.0/1e6



    for f in freqs:
        code_spec[( (code_freqs > f[0]) & (code_freqs < f[1]))]=1.0


    wlen=int(sample_rate/roll_off)
    print(wlen)
    window=ss.hann(wlen)
    window=window/n.sqrt(n.sum(window**2.0))
    print("conv")
    code_spec=n.fft.ifft(n.fft.fft(window,len(code_spec))*n.fft.fft(code_spec)).real
    # normalize to unity
    code_spec=code_spec/n.max(code_spec)
    code_spec[code_spec < 1e-5]=0.0
    print("done")

    if plot:
        plt.plot(code_freqs,code_spec**2.0)
        plt.xlabel("Frequency (MHz)")
        plt.ylabel("Spectral amplitude")
        plt.title("Desired power spectrum for transmit waveform")
        plt.show()
    return(code_freqs,code_spec)

def code_design(sample_rate=10e6,
                code_length_sec=0.1,
                max_amp=n.sqrt(2.0),
                min_amp=n.sqrt(0.5)):
    """
    Design a periodic waveform that has power only on predefined bands. This is in essense a "spread spectrum" code,
    which over the length of the code uses all of the available spectrum that it is allowed to.

    One important added constraint is that the code needs to be fairly constant in amplitude,
    so that the transmit amplifier saturation does not put high limitations on the mean
    power that can be transmitted. max_amp and min_amp specify the minimum and maximum amplitude relative to the mean amplitude.
    """

    # get the specification for the spectral mask that we are allowed to transmit in.
    f,s=get_spec(sample_rate=sample_rate,code_length_sec=code_length_sec,plot=True)

    code_len=len(s)

    # create random initial try for code
    code = n.zeros(code_len,dtype=n.complex64)

    # initialize the code randomly
    code[:]=n.random.randn(code_len)+1j*n.random.randn(code_len)

    s_shift=n.fft.fftshift(s)

    out_of_band_idx=n.where(s_shift == 0.0)[0]
    in_band_idx=n.where(s_shift > 0.0)[0]


    for i in range(200):
        # what is the periodic spectrum of the code?
        C=n.fft.fft(code)
        # project code to a code that matches the spectral shape
        C_p=C*s_shift/n.abs(C)
        code=n.fft.ifft(C_p)
        mean_amp=n.mean(n.abs(code))

        # project code to a unit amplitude code
        idx=n.where(n.abs(code)>max_amp*mean_amp)[0]
        code[idx] = max_amp*mean_amp*code[idx]/n.abs(code[idx])

        idx=n.where(n.abs(code)<min_amp*mean_amp)[0]
        code[idx] = min_amp*mean_amp*code[idx]/n.abs(code[idx])

        out_of_band_pwr=n.sum(n.abs(n.fft.fft(code))[out_of_band_idx]**2.0)/len(out_of_band_idx)
        in_band_pwr=n.sum(n.abs(n.fft.fft(code))[in_band_idx]**2.0)/len(in_band_idx)
        ratio_dB=10.0*n.log10(out_of_band_pwr/in_band_pwr)

        print("code amplitude min %1.3g max %1.3g mean %1.3g std %1.3g\nout of band power=%1.3g"%(n.min(n.abs(code)),
                                                                                                  n.max(n.abs(code)),
                                                                                                  n.mean(n.abs(code)),
                                                                                                  n.std(n.abs(code)),
                                                                                                  ratio_dB))



    plt.plot(code[0:1000].real,label="real")
    plt.plot(code[0:1000].imag,label="imag")
    plt.legend()
    plt.xlabel("Time (samples)")
    plt.ylabel("Complex amplitude")
    plt.title("Transmit code complex amplitude")
    plt.show()
    plt.plot(n.abs(code[0:1000]))
    plt.ylim([0,1.2*n.max(n.abs(code[0:1000]))])
    plt.xlabel("Time (samples)")
    plt.ylabel("Code magnitude")
    plt.title("Transmit code magnitude")
    plt.show()
    plt.plot(f,10.0*n.log10(n.abs(n.fft.fftshift(n.fft.fft(code)))**2.0))
    plt.xlabel("Freuqncy (MHz)")
    plt.ylabel("Spectrum (dB)")
    plt.title("Actual power spectrum of the code")
    plt.show()

if __name__ == "__main__":
    code_design()
