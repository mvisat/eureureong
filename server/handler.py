import threading
import select
import json

from common import protocol


class Handler:

    def __init__(self, server, connection):
        self.verbose = True
        self.server = server
        self.connection = connection

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
        if self.server.is_playing:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: protocol.STATUS_FAIL_PLAYING
            })
            self.connection.send(data)
            return

        if protocol.PLAYER_USERNAME not in message:
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
                protocol.DESCRIPTION: protocol.STATUS_FAIL_PLAYER_EXISTS
            })
            self.connection.send(data)
            return
        elif not username:
            data = json.dumps({
                protocol.STATUS: protocol.STATUS_FAIL,
                protocol.DESCRIPTION: "ga boleh kosong"
            })
            self.connection.send(data)
            return

        with self.server.lock:
            for i in range(len(self.server.usernames)):
                if self.server.usernames[i]:
                    continue

                self.server.usernames[i] = username
                data = json.dumps({
                    protocol.STATUS: protocol.STATUS_OK,
                    protocol.PLAYER_ID: i
                })
                self.connection.send(data)
                break
