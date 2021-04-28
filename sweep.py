#!/usr/bin/env python3
import numpy as n


class sweep():
    def __init__(self,
                 freqs,    # list of frequencies. three values per frequency: center_freq, code idx
                 freq_dur,
                 codes=["waveforms/code-l10000-b10-000000f_100k.bin",  # code 0
                        "waveforms/code-l10000-b10-000000f_50k.bin",   # code 1
                        "waveforms/code-l10000-b10-000000f_30k.bin"],  # code 2
                 sample_rate=1000000,  # In Hz
                 code_amp=0.5):

        self.freq_dur=freq_dur
        self.n_freqs=len(freqs)
        self.freqs=freqs
        self.codes=codes
        self.transmit_waveforms=[]
        self.code_len = 0
        self.sample_rate=sample_rate
        # check code lengths
        for c in codes:
            wf=n.fromfile(c, dtype=n.complex64)
            if self.code_len == 0:
                self.code_len=len(wf)
            else:
                if len(wf) != self.code_len:
                    print("Error. Not all waveforms are the same length!")
                    exit(0)

        n_reps=int(self.freq_dur*self.sample_rate/self.code_len)

        # todo: use waveforms created in iono_config
        for c in codes:
            wf=code_amp*n.fromfile(c, dtype=n.complex64)
            self.transmit_waveforms.append(n.tile(wf, n_reps))

        self.determine_sweep_length()
        self.t0=n.arange(self.n_freqs, dtype=n.float)*self.freq_dur

    def determine_sweep_length(self):
        """
        how long is a sweep
        """
        self.n_minutes=n.ceil((self.n_freqs*self.freq_dur)/60.0)
        # how many sweeps per day
        self.n_sweeps=n.floor(24*60/self.n_minutes)
        # how long is one ionosonde sweep
        self.sweep_len=24*60/self.n_sweeps
        self.sweep_len_s=self.sweep_len*60

    def t0s(self):
        """ relative cycle start times  """
        return(self.t0)

    def freq(self, i):
        """ center freq for cycle i  """
        return(self.freqs[i % self.n_freqs][0]*1e6)

    def waveform(self, i):
        """ get waveform array for cycle i """
        code_idx=self.freqs[i % self.n_freqs][1]
        return(self.transmit_waveforms[code_idx])

    def pars(self, i):
        """ freq, time for cycle i """
        return(self.freq(i), self.t0[i % self.n_freqs])

    def code(self, i):
        """ what code is being transmitted on cycle i """
        return(self.codes[self.freqs[i % self.n_freqs][1]])

    def code_idx(self, i):
        """ what code is being transmitted on cycle i """
        return(self.freqs[i % self.n_freqs][1])

#    def bw(self,i):
#        return(self.freqs[i][1]-self.freqs[i][0])
