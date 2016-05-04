import socket
import select
import threading
import time
import json
import random

from client.handler import Handler
from common import protocol


class Client:

    def __init__(self, host, port, verbose=None):
        self.verbose = verbose
        self.keep_running = True
        self.poll_time = 0.1

        self.handler = Handler(self)
        self.connection = Connection(self, self.handler, host, port)
        self.cv = threading.Condition()

    def close(self):
        if not self.keep_running:
            return
        self.keep_running = False
        self.connection.close()

    def join(self, username):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_JOIN,
            protocol.PLAYER_USERNAME: username,
            protocol.PLAYER_UDP_ADDRESS: self.connection.address,
            protocol.PLAYER_UDP_PORT: self.connection.port
        })
        self.server_state = protocol.METHOD_JOIN
        self.connection.server_send(data)

    def leave(self):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_LEAVE
        })
        self.server_state = protocol.METHOD_LEAVE
        self.connection.server_send(data)

    def ready(self):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_READY
        })
        self.server_state = protocol.METHOD_READY
        self.connection.server_send(data)

    def client_address(self):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_CLIENT_ADDRESS
        })
        self.server_state = protocol.METHOD_CLIENT_ADDRESS
        self.connection.server_send(data)

    def prepare_proposal(self, proposal_id, address):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_PREPARE_PROPOSAL,
            protocol.PROPOSAL_ID: proposal_id
        })
        self.state = protocol.METHOD_PREPARE_PROPOSAL
        self.connection.send(data, address, unreliable=True)

    def prepare_proposal_accept(self, proposal_id, previous_accepted_kpu_id, address):
        data = {
            protocol.STATUS: protocol.STATUS_OK,
            protocol.DESCRIPTION: protocol.DESC_ACCEPTED,
        }
        if previous_accepted_kpu_id is not None:
            data[protocol.KPU_PREV_ACCEPTED] = previous_accepted_kpu_id
        self.connection.send(json.dumps(data), address, unreliable=True)

    def prepare_proposal_reject(self, proposal_id, address):
        data = {
            protocol.STATUS: protocol.STATUS_FAIL,
            protocol.DESCRIPTION: protocol.DESC_REJECTED
        }
        self.connection.send(json.dumps(data), address, unreliable=True)

    def accept_proposal(self, proposal_id, kpu_id, address):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_ACCEPT_PROPOSAL,
            protocol.PROPOSAL_ID: proposal_id,
            protocol.KPU_ID: kpu_id
        })
        self.state = protocol.METHOD_ACCEPT_PROPOSAL
        self.connection.send(data, address, unreliable=True)

    def accept_proposal_accept(self, kpu_id, address):
        data = json.dumps({
            protocol.STATUS: protocol.STATUS_OK,
            protocol.DESCRIPTION: protocol.DESC_ACCEPTED
        })
        self.connection.send(data, address, unreliable=True)

        data = json.dumps({
            protocol.METHOD: protocol.METHOD_ACCEPTED_PROPOSAL,
            protocol.KPU_ID: kpu_id,
            protocol.DESCRIPTION: protocol.DESC_KPU_SELECTED
        })
        self.server_state = protocol.METHOD_ACCEPTED_PROPOSAL
        self.connection.server_send(data)

    def accept_proposal_reject(self, address):
        data = json.dumps({
            protocol.STATUS: protocol.STATUS_FAIL,
            protocol.DESCRIPTION: protocol.DESC_REJECTED
        })
        self.connection.send(data, address, unreliable=True)

    def vote_civilian(self, player_id, address):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_VOTE_CIVILIAN,
            protocol.PLAYER_ID: player_id
        })
        self.state = protocol.METHOD_VOTE_CIVILIAN
        self.connection.send(data, address)

    def vote_werewolf(self, player_id, address):
        data = json.dumps({
            protocol.METHOD: protocol.METHOD_VOTE_WEREWOLF,
            protocol.PLAYER_ID: player_id
        })
        self.state = protocol.METHOD_VOTE_WEREWOLF
        self.connection.send(data, address)

    def vote_result_civilian(self, vote_status, vote_result, player_killed=None):
        data = {
            protocol.METHOD: protocol.METHOD_VOTE_RESULT_CIVILIAN,
            protocol.VOTE_STATUS: vote_status,
            protocol.VOTE_RESULT: vote_result
        }
        if player_killed is not None:
            data[protocol.PLAYER_KILLED] = player_killed
        data = json.dumps(data)
        self.server_state = protocol.METHOD_VOTE_RESULT_CIVILIAN
        self.connection.server_send(data)

    def vote_result_werewolf(self, vote_status, vote_result, player_killed=None):
        data = {
            protocol.METHOD: protocol.METHOD_VOTE_RESULT_WEREWOLF,
            protocol.VOTE_STATUS: vote_status,
            protocol.VOTE_RESULT: vote_result
        }
        if player_killed is not None:
            data[protocol.PLAYER_KILLED] = player_killed
        data = json.dumps(data)
        self.server_state = protocol.METHOD_VOTE_RESULT_CIVILIAN
        self.connection.server_send(data)

class Connection:

    def __init__(self, client, handler, host, port):
        self.buf_size = 1024
        self.timeout = 0.5

        self.client = client
        self.handler = handler

        # connect to server host:port
        self.server_host = host
        self.server_port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.connect((self.server_host, self.server_port))
        self.server_socket.setblocking(0)

        # workaround to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 0))
            self.address = s.getsockname()[0]
        except:
            self.address = '127.0.0.1'
        finally:
            s.close()

        # randomize client udp port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', 0))
        _, self.port = self.socket.getsockname()
        self.client.verbose and print("Listening UDP at %s:%d" % (self.address, self.port))

        self.lock = threading.Lock()
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
                    with self.client.cv:
                        self.client.cv.notify_all()
                    break

                message = data.decode('utf-8').strip("\n")
                messages.append(message)

                if message.endswith(protocol.PROTOCOL_END):
                    message = self._split("".join(messages))
                    for m in message:
                        self.client.verbose and print("Recv:", m)
                        self.handler.server_handle(m)
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
                        self.handler.handle(m, address)
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

    def send(self, message, address, unreliable=False):
        if unreliable and random.randint(1, 100) >= 75:
            self.client.verbose and print("Send to %s:%d: Failed (unreliable)" % (address))
            return

        if not self._send(message, address):
            self.client.keep_running = False
