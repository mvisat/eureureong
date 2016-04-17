#!/usr/bin/python3

import argparse

from server import server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port", type=int, help="port to bind")
    args = parser.parse_args()

    server.Server(port=args.port).serve_forever()

if __name__ == '__main__':
    main()
