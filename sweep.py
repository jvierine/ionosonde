import numpy as n


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

# 30 freq sweep
freqs30=[[2.2,2.3],     
         [2.35,2.45],   
         [2.51,2.61],
         [2.65,2.75],
         [3.155,3.255],
         [3.3,3.4],
         [3.95,4.0],     # 50 kHz
         [4.438,4.538],  
         [4.6,4.65],     # 50 kHz
         [4.85,4.95],
         [5.005,5.105],
         [5.155,5.255],
         [5.305,5.335],
         [5.4,5.45],
         [5.8,5.9],
         [5.95,6.05],
         [6.1,6.2],
         [6.8,6.85],     # 50 kHz
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
         [17.48,17.58]]

freqs60=[[2.2,2.3],
         [3.155,3.255],
         [3.95,4.0],
         [4.6,4.65],
         [5.005,5.105],
         [5.4,5.45]]


class sweep():
    def __init__(self,freqs,freq_dur):
        self.freq_dur=freq_dur
        self.n_freqs=len(freqs)
        self.freqs=freqs
        
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

    def pars(self,i):
        return(self.freq(i),self.t0[i%self.n_freqs])
    
