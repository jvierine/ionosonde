#!/usr/bin/env python3

import argparse
import iono_config


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config',
        default="config/default.ini",
        help='''Configuration file. (default: %(default)s)''',
    )
    parser.add_argument(
        '-w', '--create_waveforms',
        default=False,
        action="store_true",
        help='''Create waveform files. (default: %(default)s)''',
    )
    op = parser.parse_args()

    c = iono_config.get_config(config=op.config, write_waveforms=op.create_waveforms)
    print(c)
    print("Configuration file is good")
