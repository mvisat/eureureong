import threading
import select
import json

from common import protocol


class Handler:

    def __init__(self, server, connection):
        self.verbose = True
        self.server = server
        self.connection = connection

        self.player_id = None
        self.username = None

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

    def handle(self, messages):
        messages = self._split(messages)
        for message in messages:
            if protocol.METHOD not in message:
                continue

            # call corresponding method, if exists
            method = message[protocol.METHOD]
            handle_method = getattr(self, "handle_" + method, None)
            if callable(handle_method):
                handle_method(message)
            else:
                self.verbose and print(
                    "Error: Method '%s' not implemented" % method)

    def handle_join(self, message):
        if self.player_id is not None:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.DESC_ALREADY_JOINED
            })
            self.connection.send(data)
            return

        elif self.server.is_playing:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.DESC_GAME_IS_PLAYING
            })
            self.connection.send(data)
            return

        elif self.server.player_count >= self.server.MAX_PLAYER:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.DESC_SERVER_IS_FULL
            })
            self.connection.send(data)
            return

        elif (protocol.PLAYER_USERNAME not in message or
                protocol.PLAYER_UDP_ADDRESS not in message or
                protocol.PLAYER_UDP_PORT not in message):
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_ERROR,
                protocol.DESCRIPTION: protocol.DESC_WRONG_REQUEST
            })
            self.connection.send(data)
            return

        try:
            username = str(message[protocol.PLAYER_USERNAME]).strip()
            address = str(message[protocol.PLAYER_UDP_ADDRESS]).strip()
            port = int(message[protocol.PLAYER_UDP_PORT])
        except ValueError:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_ERROR,
                protocol.DESCRIPTION: protocol.DESC_WRONG_REQUEST
            })
            self.connection.send(data)
            return

        if username in self.server.usernames:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.DESC_USERNAME_EXISTS
            })
            self.connection.send(data)
            return
        elif not username:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.DESC_USERNAME_BLANK
            })
            self.connection.send(data)
            return

        with self.server.lock:
            i = self.server.id_taken.index(False)

            self.player_id = i
            self.username = username

            self.server.player_count += 1
            self.server.ids.append(i)
            self.server.usernames.add(username)
            self.server.id_taken[i] = True
            self.server.is_ready[i] = False
            self.server.is_alive[i] = True
            self.server.is_werewolf[i] = False
            self.server.player_name[i] = username
            self.server.player_connection[i] = self.connection
            self.server.player_address[i] = address
            self.server.player_port[i] = port

        data = json.dumps({
            protocol.STATUS: protocol.STATUS_OK,
            protocol.PLAYER_ID: self.player_id
        })
        self.connection.send(data)

    def handle_leave(self, message=None):
        if self.player_id is None:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.DESC_NOT_JOINED
            })
            self.connection.send(data)
            return

        with self.server.lock:
            self.server.player_count -= 1
            if self.player_id in self.server.ids:
                self.server.ids.remove(self.player_id)
            if self.username in self.server.usernames:
                self.server.usernames.remove(self.username)
            self.server.id_taken[self.player_id] = False
            self.server.is_ready[self.player_id] = False
            self.server.is_alive[self.player_id] = False
            self.server.is_werewolf[self.player_id] = False
            self.server.player_name[self.player_id] = None
            self.server.player_connection[self.player_id] = None

            self.username = None
            self.player_id = None
        data = json.dumps({
            protocol.STATUS: protocol.STATUS_OK
        })
        self.connection.send(data)

    def handle_ready(self, message=None):
        if self.player_id is None:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.DESC_NOT_JOINED
            })
            self.connection.send(data)
            return
        elif self.server.is_playing:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.DESC_GAME_IS_PLAYING
            })
            self.connection.send(data)
            return
        elif self.server.is_ready[self.player_id]:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.DESC_WERE_READY
            })
            self.connection.send(data)
            return

        with self.server.lock:
            self.server.is_ready[self.player_id] = True
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_OK,
                protocol.DESCRIPTION: protocol.DESC_WAIT_TO_START
            })
            self.connection.send(data)

            if (self.server.player_count >= self.server.MIN_PLAYER and
                    self.server.player_count == self.server.is_ready.count(True)):
                self.server.start_game()

    def handle_client_address(self, message=None):
        with self.server.lock:
            clients = [{
                protocol.PLAYER_ID: i,
                protocol.PLAYER_IS_ALIVE: 1 if self.server.is_alive[i] else 0,
                protocol.PLAYER_ADDRESS: self.server.player_address[i],
                protocol.PLAYER_PORT: self.server.player_port[i],
                protocol.PLAYER_USERNAME: self.server.player_name[i]
                } for i in self.server.ids
            ]
            for i, client in enumerate(clients):
                player_id = client[protocol.PLAYER_ID]
                if not self.server.is_alive[player_id]:
                    role = protocol.ROLE_WEREWOLF if self.server.is_werewolf[player_id] else protocol.ROLE_CIVILIAN
                    clients[i][protocol.ROLE] = role
        data = json.dumps({
            protocol.STATUS: protocol.STATUS_OK,
            protocol.DESCRIPTION: protocol.DESC_CLIENT_LIST,
            protocol.CLIENTS: clients
        })
        self.connection.send(data)

    def handle_accept_proposal(self, message):
        if self.player_id is None:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.DESC_NOT_JOINED
            })
            self.connection.send(data)
            return

        elif protocol.KPU_ID not in message:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_ERROR,
                protocol.DESCRIPTION: protocol.DESC_WRONG_REQUEST
            })
            self.connection.send(data)
            return

        kpu_id = message[protocol.KPU_ID]
        self.server.vote_kpu_id[self.player_id] = kpu_id

        quorum = (self.server.player_count - 2) // 2 + 1
        set_kpu_id = set(self.server.vote_kpu_id)
        for kpu_id in set_kpu_id:
            if kpu_id is None:
                continue
            if self.server.vote_kpu_id.count(kpu_id) >= quorum:
                self.server.selected_kpu_id = kpu_id
                self.server.kpu_selected(kpu_id)
                self.server.vote_now()
                return

    def handle_vote_result_civilian(self, message):
        if self.player_id is None:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.DESC_NOT_JOINED
            })
            self.connection.send(data)
            return

        elif protocol.VOTE_STATUS not in message:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_ERROR,
                protocol.DESCRIPTION: protocol.DESC_WRONG_REQUEST
            })
            self.connection.send(data)
            return

        elif protocol.VOTE_RESULT not in message:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_ERROR,
                protocol.DESCRIPTION: protocol.DESC_WRONG_REQUEST
            })
            self.connection.send(data)
            return

        vote_status = message[protocol.VOTE_STATUS]
        if vote_status > 0:
            if protocol.PLAYER_KILLED not in message:
                data = json.dumps({
                    protocol.STATUS: protocol.STATUS_ERROR,
                    protocol.DESCRIPTION: protocol.DESC_WRONG_REQUEST
                })
                self.connection.send(data)
                return
            player_killed = message[protocol.PLAYER_KILLED]
            self.server.is_alive[player_killed] = False
            self.server.change_phase()
        else:
            self.server.vote_now()

    def handle_vote_result_werewolf(self, message):
        self.handle_vote_result_civilian(message)
