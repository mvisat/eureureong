import threading
import select
import json

from common import protocol


class Handler:

    def __init__(self, server, socket, addr):
        self.server = server
        self.socket = socket
        self.addr = addr
        self.buf_size = 4096
        self.verbose = True

        self.keep_running = True
        self.thread = threading.Thread(target=self.recv)
        self.thread.start()

    def close(self):
        self.keep_running = False
        self.socket.close()

    def recv(self):
        while self.keep_running and self.server.keep_running:
            try:
                messages = list()
                while self.keep_running and self.server.keep_running:

                    # check socket if it is ready to read
                    readable, _, _ = select.select([self.socket], [], [], 0.5)
                    if self.socket not in readable:
                        continue

                    # receive the packet
                    message = self.socket.recv(self.buf_size).decode('utf-8')

                    # client is disconnected
                    if not message:
                        self.verbose and print(
                            "Client", str(self.addr),
                            "disconnected, exiting...")
                        self.close()
                        return

                    # strip extra newline, continue if empty
                    message = message.strip("\n")
                    if not message:
                        continue

                    messages.append(message)
                    self.verbose and print(
                        "Received", len(message), "bytes:", message)

                    # keep recv until PROTOCOL_END is received
                    if message.endswith(protocol.PROTOCOL_END):
                        break

                messages = "".join(messages)
                self.handle(messages)

            except select.error:
                pass

            except Exception as e:
                print(e)
                break

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
