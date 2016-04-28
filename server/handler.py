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

    def handle(self, messages):
        try:
            idx = messages.find(protocol.PROTOCOL_END)
            while idx >= 0:
                # split message from PROTOCOL_END marker
                message = messages[:idx+1]
                messages = messages[idx+1:]

                # try to load as json, check if method is in message
                message = json.loads(message)
                if protocol.METHOD not in message:
                    return

                # call corresponding method, if exists
                method = message[protocol.METHOD]
                handle_method = getattr(self, "handle_" + method, None)
                if callable(handle_method):
                    handle_method(message)
                else:
                    self.verbose and print(
                        "Error: Method '%s' not implemented" % method)

                # continue find PROTOCOL_END
                idx = messages.find(protocol.PROTOCOL_END)

        except (ValueError, KeyError) as e:
            pass

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
        data = json.dumps({
            protocol.STATUS: protocol.STATUS_OK,
            protocol.DESCRIPTION: protocol.DESC_CLIENT_LIST,
            protocol.CLIENTS: clients
        })
        self.connection.send(data)
