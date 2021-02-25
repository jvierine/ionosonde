#! /usr/bin/env python3

import os
from datetime import datetime, timedelta
from pathlib import Path


class logger:
    def __init__(self, prefix):
        self.logdir = Path("log")
        self.logdir.mkdir(exist_ok=True)

        self.creation_time = datetime.utcnow()
        self.prefix = prefix
        fname = self.logdir / ("%s%s" % (self.prefix, self.creation_time.strftime("%FT%T.log")))
        self.f = open(fname, "w")

        current_log = Path("%scurrent.log" % prefix)
        if current_log.exists():
            current_log.unlink()
        current_log.symlink_to(fname)

    def need_to_reopen(self):
        if self.creation_time.date() != datetime.utcnow().date():
            # New day, need to reopen logfile
            self.f.close()
            self.__init__(self.prefix)

    def log(self, msg, print_msg=True):
        self.need_to_reopen()
        if print_msg:
            print(msg)
        log_time = datetime.utcnow()
        self.f.write("%s %s\n" % (log_time.strftime("%FT%T"), msg))
        self.f.flush()
