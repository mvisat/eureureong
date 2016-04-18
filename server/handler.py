import threading
import select
import json

from common import protocol


class Handler:

    def __init__(self, server):
        self.server = server

    def handle(self, client_socket, messages):
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
