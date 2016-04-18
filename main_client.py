#!/usr/bin/python3

import argparse
import threading
import time

from client.client import Client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("host", type=str, help="server host")
    parser.add_argument("port", type=int, help="server port")
    args = parser.parse_args()

    client = Client(args.host, args.port)
    try:
        while client.keep_running:
            time.sleep(1)
    except:
        pass    

if __name__ == "__main__":
    main()
