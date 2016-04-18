import socket
import threading

from common import protocol
from server.handler import Handler


class Server:

    def __init__(self, host='', port=9999):
        self.verbose = True
        self.keep_running = True

        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(6)
        self.handlers = []

    def serve_forever(self):
        try:
            while self.keep_running:
                self.verbose and print("Listening client connection...")
                client_socket, client_addr = self.socket.accept()

                self.verbose and print("Get connection from", str(client_addr))
                handler = Handler(self, client_socket, client_addr)
                self.handlers.append(handler)

        except KeyboardInterrupt:
            self.verbose and print("Terminated by user")
            self.keep_running = False

        finally:
            for handler in self.handlers:
                h.close()
            self.socket.close()

    def close(self):
        self.keep_running = False
