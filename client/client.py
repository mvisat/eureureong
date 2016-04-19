import socket
import select
import threading
import json

from client.handler import Handler
from common import protocol


class Client:

    def __init__(self, host, port):
        self.verbose = True
        self.keep_running = True

        self.handler = Handler(self)
        self.connection = Connection(self, self.handler, host, port)

    def close(self):
        self.connection.close()

    def join(self, username):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_JOIN,
            protocol.PLAYER_USERNAME: username
        })
        self.connection.server_send(data)

    def leave(self):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_LEAVE
        })
        self.connection.server_send(data)

    def client_address(self):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_CLIENT_ADDRESS
        })
        self.connection.server_send(data)


class Connection:

    def __init__(self, client, handler, host, port):
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

        self.lock = threading.Lock()
        self.server_thread = threading.Thread(target=self.server_recv)
        self.server_thread.start()
        self.thread = threading.Thread(target=self.recv)
        self.thread.start()

    def close(self):
        self.keep_running = False
        self.server_thread.join()
        self.thread.join()

    def server_recv(self):
        while self.keep_running:
            try:
                readable, _, _ = select.select([self.server_socket], [], [], self.timeout)
                if self.server_socket not in readable:
                    continue

                data = self.server_socket.recv(self.buf_size)

                # server disconnected
                if not data:
                    self.keep_running = False
                    break

                self.verbose and print("Recv server:", data)

            except select.error:
                break

        self.server_socket.close()

    def recv(self):
        while self.keep_running:
            try:
                readable, _, _ = select.select([self.socket], [], [], self.timeout)
                if self.socket not in readable:
                    continue

                data, address = self.socket.recvfrom(self.buf_size)

                # server disconnected
                if not data:
                    break

                self.verbose and print("Recv from", address, ":", data)

            except select.error:
                break

        self.socket.close()

    def _str_to_byte(self, s):
        if isinstance(s, bytes):
            return s
        if not isinstance(s, str):
            s = str(s)
        return s.encode()

    def _send(self, socket, message):
        message = self._str_to_byte(message)
        total_sent = 0
        while self.keep_running and total_sent < len(message):
            _, writable, _ = select.select([], [socket], [], self.timeout)
            if socket not in writable:
                continue

            self.verbose and print("Sending:", message)
            sent = socket.send(message[total_sent:])
            if sent == 0:
                return False
            total_sent += sent
        return True

    def server_send(self, message):
        if not self._send(self.server_socket, message):
            self.keep_running = False
