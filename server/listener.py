import socket
import threading

from common import protocol
from server import handler
from server import server


class listener:
    def __init__(self, host='', port=9999):
        self.__verbose = True
        self.host = host
        self.port = port
        self.server = server.server()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(6)
        self.__handler_lock = threading.Lock()
        self.client_handlers = []

    def serve_forever(self):
        try:
            while self.server.keep_running:
                self.__verbose and print("Listening client connection...")
                client_socket, client_addr = self.socket.accept()
                with self.server.handlers_lock:
                    self.__verbose and print(
                        "Get connection from", str(client_addr))
                    self.server.handlers.append(
                        handler.handler(
                            self.server, client_socket, client_addr))

        except KeyboardInterrupt:
            self.__verbose and print("Terminated by user")
            self.server.keep_running = False

        finally:
            for client_handler in self.client_handlers:
                client_handler.close()
            self.socket.close()

    def close(self):
        self.__keep_running = False
