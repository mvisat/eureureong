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

        elif protocol.PLAYER_USERNAME not in message:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_ERROR,
                protocol.DESCRIPTION: protocol.STATUS_ERROR_WRONG_REQ
            })
            self.connection.send(data)
            return

        username = message[protocol.PLAYER_USERNAME]
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
            for i in range(self.server.MAX_PLAYER):
                if self.server.id_taken[i]:
                    continue

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

                data = json.dumps({
                    protocol.STATUS: protocol.STATUS_OK,
                    protocol.PLAYER_ID: i
                })
                self.connection.send(data)
                break

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
