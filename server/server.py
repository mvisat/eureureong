import socket
import select
import threading
import json

import random
import time

from common import protocol
from server.handler import Handler


class Server:

    def __init__(self, host='', port=9999):
        self.verbose = True
        self.keep_running = True
        self.timeout = 1

        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(6)

        self.lock = threading.Lock()
        self.client_sockets = []
        self.client_addrs = []
        self.connections = []

        self._init_game()
        self.reset_game()

        random.seed()

    def _init_game(self):
        self.MIN_PLAYER = 6
        self.MAX_PLAYER = 8
        self.MAX_WEREWOLF = 2

        self.player_count = 0
        self.ids = []
        self.usernames = set()
        self.id_taken = [False] * self.MAX_PLAYER
        self.player_name = [None] * self.MAX_PLAYER
        self.player_connection = [None] * self.MAX_PLAYER
        self.player_address = [None] * self.MAX_PLAYER
        self.player_port = [None] * self.MAX_PLAYER

        self.selected_kpu_id = None
        self.vote_kpu_id = [None] * self.MAX_PLAYER

    def reset_game(self):
        self.is_playing = False
        self.day = 0
        self.time = protocol.TIME_NIGHT
        self.is_ready = [False] * self.MAX_PLAYER
        self.is_alive = [True] * self.MAX_PLAYER
        self.is_werewolf = [False] * self.MAX_PLAYER

    def serve_forever(self):
        try:
            self.verbose and print("Listening to client connections...")
            while self.keep_running:
                readable, _, _ = select.select([self.socket], [], [], self.timeout)
                if self.socket not in readable:
                    continue

                client_socket, client_addr = self.socket.accept()
                self.verbose and print("Get connection from", str(client_addr))

                self.client_sockets.append(client_socket)
                self.client_addrs.append(client_addr)

                connection = Connection(self, client_socket, client_addr)
                self.connections.append(connection)
                connection.start()

        except KeyboardInterrupt:
            self.verbose and print("Terminated by user")

        finally:
            self.keep_running = False
            for connection in self.connections:
                connection.join()
            self.socket.close()

    def close(self):
        self.keep_running = False

    def broadcast(self, message):
        for pid in self.ids:
            connection = self.player_connection[pid]
            if connection:
                connection.send(message)

    def start_game(self):
        if self.is_playing or self.player_count < self.MIN_PLAYER:
            return

        self.verbose and print("Starting the game...")
        self.is_playing = True

        candidate = list(self.ids)
        for i in range(self.MAX_WEREWOLF):
            x = random.randint(0, len(candidate)-1)
            self.is_werewolf[candidate[x]] = True
            del candidate[x]

        for pid in self.ids:
            data = {
                protocol.METHOD: protocol.METHOD_START,
                protocol.TIME: self.time,
                protocol.DESCRIPTION: protocol.DESC_GAME_START
            }
            if self.is_werewolf[pid]:
                friends = [
                    self.player_name[i]
                    for i in self.ids
                    if i != pid and self.is_werewolf[i]
                ]
                data[protocol.ROLE] = protocol.ROLE_WEREWOLF
                data[protocol.FRIEND] = friends
            else:
                data[protocol.ROLE] = protocol.ROLE_CIVILIAN

            connection = self.player_connection[pid]
            if connection:
                connection.send(data)

        self.change_phase()

    def change_phase(self):
        werewolves = [i for i in range(self.MAX_PLAYER) if self.is_alive[i] and self.is_werewolf[i]]
        civilians = [i for i in range(self.MAX_PLAYER) if self.is_alive[i] and not self.is_werewolf[i]]
        if len(werewolves) == 0:
            self.game_over(protocol.ROLE_CIVILIAN)
            self.close()
            return
        elif len(werewolves) >= len(civilians):
            self.game_over(protocol.ROLE_WEREWOLF)
            self.close()
            return

        if self.time == protocol.TIME_NIGHT:
            self.time = protocol.TIME_DAY
            self.day += 1
            self.retry_vote = 2
        else:
            self.time = protocol.TIME_NIGHT

        data = {
            protocol.METHOD: protocol.METHOD_CHANGE_PHASE,
            protocol.TIME: self.time,
            protocol.DAYS: self.day
        }
        self.broadcast(data)

    def kpu_selected(self, kpu_id):
        data = {
            protocol.METHOD: protocol.METHOD_KPU_SELECTED,
            protocol.KPU_ID: kpu_id
        }
        self.broadcast(data)

    def vote_now(self):
        if self.time == protocol.TIME_DAY:
            if self.retry_vote > 0:
                self.retry_vote -= 1
            else:
                self.change_phase()
                return
        data = {
            protocol.METHOD: protocol.METHOD_VOTE_NOW,
            protocol.PHASE: self.time
        }
        self.broadcast(data)

    def game_over(self, winner):
        data = {
            protocol.METHOD: protocol.METHOD_GAME_OVER,
            protocol.WINNER: winner,
            protocol.DESCRIPTION: "Winner is %s." % (winner)
        }
        self.broadcast(data)

class Connection(threading.Thread):

    def __init__(self, server, client_socket, client_addr):
        super().__init__()

        self.verbose = True
        self.buf_size = 2048
        self.timeout = 1

        self.server = server
        self.socket = client_socket
        self.addr = client_addr
        self.handler = Handler(server, self)

    def run(self):
        messages = []
        while self.server.keep_running:
            try:
                # check socket if it is ready to read
                readable, _, _ = select.select([self.socket], [], [], self.timeout)
                if self.socket not in readable:
                    continue

                # receive the packet
                message = self.socket.recv(self.buf_size)

                # client is disconnected
                if not message:
                    self.verbose and print(
                        "Client", str(self.addr),
                        "disconnected, exiting...")
                    break

                # decode and strip extra newline, continue if empty
                message = message.decode('utf-8').strip("\n")
                if not message:
                    continue

                messages.append(message)
                self.verbose and print(
                    "Received", len(message), "bytes:", message)

                # keep recv until PROTOCOL_END is received
                if not message.endswith(protocol.PROTOCOL_END):
                    continue

                full_message = "".join(messages)
                self.handler.handle(full_message)
                messages.clear()

            except select.error:
                break

            except Exception as e:
                print(e)
                break

        self.handler.handle_leave()
        self.socket.close()

    def send(self, message):
        if isinstance(message, bytes):
            pass
        elif isinstance(message, str):
            message = message.encode()
        else:
            message = json.dumps(message).encode()

        total_sent = 0
        while self.server.keep_running and total_sent < len(message):
            _, writable, _ = select.select([], [self.socket], [], self.timeout)
            if self.socket not in writable:
                continue

            self.verbose and print("Sending:", message)
            sent = self.socket.send(message[total_sent:])
            if sent == 0:
                break
            total_sent += sent
