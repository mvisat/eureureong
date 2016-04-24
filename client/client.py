import socket
import select
import threading
import time
import json

from client.handler import Handler
from common import protocol


class Client:

    def __init__(self, host, port):
        self.verbose = True
        self.keep_running = True
        self.poll_time = 0.1

        self.handler = Handler(self)
        self.connection = Connection(self, self.handler, host, port)

        self.server_last_messages = []
        self.last_messages = {}

    def close(self):
        if not self.keep_running:
            return
        self.keep_running = False
        self.connection.close()

    def server_recv(self):
        while self.keep_running and not self.connection.server_messages:
            time.sleep(self.poll_time)
        if self.connection.server_messages:
            return self.connection.server_messages.pop(0)
        else:
            return None

    def recv(self):
        while self.keep_running and not self.connection.messages:
            time.sleep(self.poll_time)
        if self.connection.messages:
            return self.connection.messages.pop(0)
        else:
            return None

    def join(self, username):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_JOIN,
            protocol.PLAYER_USERNAME: username,
            protocol.PLAYER_PORT: self.connection.port
        })
        self.connection.server_send(data)
        return self.server_recv()

    def leave(self):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_LEAVE
        })
        self.connection.server_send(data)
        return self.server_recv()

    def ready(self):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_READY
        })
        self.connection.server_send(data)
        return self.server_recv()

    def client_address(self):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_CLIENT_ADDRESS
        })
        self.connection.server_send(data)
        return self.server_recv()

    def prepare_proposal(self, proposal_id, address):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_PREPARE_PROPOSAL,
            protocol.PROPOSAL_ID: proposal_id
        })
        self.connection.send(data, address)


class Connection:

    def __init__(self, client, handler, host, port):
        self.buf_size = 1024
        self.timeout = 0.5

        self.client = client

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
        self.client.verbose and print("Listening UDP at %s:%d" % (self.host, self.port))

        self.lock = threading.Lock()
        self.server_messages = []
        self.messages = []
        self.server_thread = threading.Thread(target=self.server_recv)
        self.server_thread.start()
        self.thread = threading.Thread(target=self.recv)
        self.thread.start()

    def close(self):
        self.server_thread.join()
        self.thread.join()

    def _split(self, messages):
        last_messages = []
        idx = messages.find(protocol.PROTOCOL_START)
        while idx >= 0:
            level = 1
            for i in range(idx+1, len(messages)):
                if messages[i] == protocol.PROTOCOL_START:
                    level += 1
                elif messages[i] == protocol.PROTOCOL_END:
                    level -= 1
                    if level == 0:
                        idx = i
                        break
            # split message from PROTOCOL_END marker
            message = messages[:idx+1]
            messages = messages[idx+1:]

            # try to load as json
            message = json.loads(message)
            last_messages.append(message)

            # continue find PROTOCOL_END
            idx = messages.find(protocol.PROTOCOL_END)

        return last_messages

    def server_recv(self):
        messages = []
        while self.client.keep_running:
            try:
                readable, _, _ = select.select([self.server_socket], [], [], self.timeout)
                if self.server_socket not in readable:
                    continue

                data = self.server_socket.recv(self.buf_size)

                # server disconnected
                if not data:
                    self.client.keep_running = False
                    break

                message = data.decode('utf-8').strip("\n")
                messages.append(message)

                if message.endswith(protocol.PROTOCOL_END):
                    message = self._split("".join(messages))
                    for m in message:
                        self.client.verbose and print("Recv:", m)
                        self.server_messages.append(m)
                    messages.clear()

            except select.error:
                break

        self.server_socket.close()

    def recv(self):
        messages = {}
        while self.client.keep_running:
            try:
                readable, _, _ = select.select([self.socket], [], [], self.timeout)
                if self.socket not in readable:
                    continue

                data, address = self.socket.recvfrom(self.buf_size)

                if not data:
                    continue

                message = data.decode('utf-8').strip("\n")
                if address not in messages:
                    messages[address] = []
                messages[address].append(message)

                if message.endswith(protocol.PROTOCOL_END):
                    message = self._split("".join(messages[address]))
                    for m in message:
                        self.client.verbose and print("Recv from %s:%d:" % (address), m)
                        self.messages.append((address, m))
                    messages[address].clear()

            except select.error:
                break

        self.socket.close()

    def _str_to_byte(self, s):
        if isinstance(s, bytes):
            return s
        if not isinstance(s, str):
            s = str(s)
        return s.encode()

    def _server_send(self, socket, message):
        message = self._str_to_byte(message)
        total_sent = 0
        while self.client.keep_running and total_sent < len(message):
            _, writable, _ = select.select([], [socket], [], self.timeout)
            if socket not in writable:
                continue

            self.client.verbose and print("Send:", message.decode('utf-8'))
            sent = socket.send(message[total_sent:])
            if sent == 0:
                return False
            total_sent += sent
        return True

    def _send(self, message, address):
        message = self._str_to_byte(message)
        total_sent = 0
        while self.client.keep_running and total_sent < len(message):
            _, writable, _ = select.select([], [self.socket], [], self.timeout)
            if self.socket not in writable:
                continue

            self.client.verbose and print("Send to %s:%d:" % (address), message.decode('utf-8'))
            sent = self.socket.sendto(message[total_sent:], address)
            if sent == 0:
                return False
            total_sent += sent
        return True

    def server_send(self, message):
        if not self._server_send(self.server_socket, message):
            self.client.keep_running = False

    def send(self, message, address):
        if not self._send(message, address):
            self.client.keep_running = False
