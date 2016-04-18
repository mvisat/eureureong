import socket
import select
import threading

from client.handler import Handler


class Client:

    def __init__(self, host, port):
        self.verbose = True
        self.keep_running = True
        self.buf_size = 1024
        self.timeout = 1

        # connect to server host:port
        self.server_host = host
        self.server_port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.connect((self.server_host, self.server_port))
        self.server_socket.setblocking(0)

        # randomize client udp port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', 0))
        self.host, self.port = self.socket.getsockname()
        self.verbose and print("Listening UDP at %s:%d" % (self.host, self.port))

        self.handler = Handler(self)
        self.lock = threading.Lock()
        self.server_thread = threading.Thread(target=self._server_recv)
        self.thread = threading.Thread(target=self._recv)

    def close(self):
        self.keep_running = False
        self.socket.close()
        self.server_socket.close()

    def _server_recv(self, server_socket):
        while self.keep_running:
            try:
                readable, _, _ = select.select([self.server_socket], [], [], self.timeout)
                if self.server_socket not in readable:
                    continue

                data = self.server_socket.recv(self.buf_size)

                # server disconnected
                if not data:
                    break

                self.verbose and print("recv_server:", data)

            except select.error:
                break

        # server is down anyway
        self.close()

    def _recv(self):
        while self.keep_running and self.client.keep_running:
            try:
                readable, _, _ = select.select([self.socket], [], [], sel.timeout)
                if self.socket not in readable:
                    continue

                data, address = self.socket.recvfrom(self.buf_size)

                # server disconnected
                if not data:
                    break

                self.verbose and print("recv from", address, ":", data)

            except select.error:
                break
