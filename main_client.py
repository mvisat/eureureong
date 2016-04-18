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
    thread_server = threading.Thread(target=client.handler.recv_server)
    thread = threading.Thread(target=client.handler.recv)
    thread_server.start()
    thread.start()
    try:
        while client.keep_running:
            time.sleep(1)
    except:
        pass
    finally:
        client.keep_running = False
        thread_server.join()
        thread.join()

if __name__ == "__main__":
    main()
