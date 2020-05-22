import numpy as n


freqs=[[2.2,2.3,0],
       [2.35,2.45,0],
       [2.51,2.61,0],
       [2.65,2.75,0],
       [3.155,3.255,0],
       [3.3,3.4,0],
       [3.95,4.0,0],
       [4.438,4.538,0],
       [4.6,4.65,0],
       [4.85,4.95,0],
       [5.005,5.105,0],
       [5.155,5.255,0],
       [5.305,5.335,0],
       [5.4,5.45,0],
       [5.8,5.9,0],
       [5.95,6.05,0],
       [6.1,6.2,0],
       [6.8,6.85,0],
       [6.9,7,0],
       [7.2,7.3,0],
       [7.35,7.45,0],
       [7.5,7.6,0],
       [7.65,7.75,0],
       [8.095,8.195,0],
       [9.4,9.5,0],
       [11.6,11.7,0],
       [13.57,13.67,0],
       [15.1,15.2,0],
       [15.7,15.8,0],
       [17.48,17.58,0],
       [18.9,19.0,0],
       [21.45,21.55,0],
       [25.01,25.11,0]]

# 30 freq sweep. the third column refers to the code index in
# the list codes passed to the sweep class
freqs30=[[2.2,2.3,0],     
         [2.35,2.45,0],   
         [2.51,2.61,0],
         [2.65,2.75,0],
         [3.155,3.255,0],
         [3.3,3.4,0],
         [3.95,4.0,1],     # 50 kHz
         [4.438,4.538,0],  
         [4.6,4.65,1],     # 50 kHz
         [4.85,4.95,0],
         [5.005,5.105,0],
         [5.155,5.255,0],
         [5.305,5.335,2],  # 30 kHz
         [5.4,5.45,1],     # 50 kHz
         [5.8,5.9,0],
         [5.95,6.05,0],
         [6.1,6.2,0],
         [6.8,6.85,1],     # 50 kHz
         [6.9,7,0],  
         [7.2,7.3,0],
         [7.35,7.45,0],
         [7.5,7.6,0],
         [7.65,7.75,0],
         [8.095,8.195,0],
         [9.4,9.5,0],
         [11.6,11.7,0],
         [13.57,13.67,0],
         [15.1,15.2,0],
         [15.7,15.8,0],
         [17.48,17.58,0]]

freqs60=[[2.2,2.3,0],
         [3.155,3.255,0],
         [3.95,4.0,0],
         [4.6,4.65,0],
         [5.005,5.105,0],
         [5.4,5.45,0]]


class sweep():
    def __init__(self,
                 freqs,    # list of frequencies. three values per frequency: min freq, max freq, code idx
                 freq_dur,
                 codes=["waveforms/code-l10000-b10-000000f_100k.bin", # code 0
                        "waveforms/code-l10000-b10-000000f_50k.bin",  # code 1
                        "waveforms/code-l10000-b10-000000f_30k.bin"], # code 2
                 sample_rate=1000000, # In Hz
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
            wf=n.fromfile(c,dtype=n.complex64)
            if self.code_len == 0:
                self.code_len=len(wf)
            else:
                if len(wf) != self.code_len:
                    print("Error. Not all waveforms are the same length!")
                    exit(0)
        
        n_reps=int(self.freq_dur*self.sample_rate/self.code_len)

        for c in codes:
            wf=code_amp*n.fromfile(c,dtype=n.complex64)
            self.transmit_waveforms.append(n.tile(wf,n_reps))
        
        self.determine_sweep_length()
        self.t0=n.arange(self.n_freqs,dtype=n.float)*self.freq_dur

    def determine_sweep_length(self):
        self.n_minutes=n.ceil((self.n_freqs*self.freq_dur)/60.0)
        # how many sweeps per day
        self.n_sweeps=n.floor(24*60/self.n_minutes)
        # how long is one ionosonde sweep
        self.sweep_len=24*60/self.n_sweeps
        self.sweep_len_s=self.sweep_len*60
        
    def t0s(self):
        return(self.t0)

    def freq(self,i):
        return(0.5*(self.freqs[i%self.n_freqs][0]+self.freqs[i%self.n_freqs][1])*1e6)
    
    def waveform(self,i):
        code_idx=self.freqs[i%self.n_freqs][2]
        return(self.transmit_waveforms[code_idx])

    def pars(self,i):
        return(self.freq(i),self.t0[i%self.n_freqs])
    
    def bw(self,i):
        return(self.freqs[i][1]-self.freqs[i][0])
    
