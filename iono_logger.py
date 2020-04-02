import time

class logger:
    def __init__(self,fname):
        self.f=open(fname,"w")
    def log(self,msg,print_msg=False):
        if print_msg:
            print(msg)
        self.f.write("%d %s\n"%(time.time(),msg))
        self.f.flush()
