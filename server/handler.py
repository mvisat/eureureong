import threading
import select
import json

from common import protocol


class handler():

    def __init__(self, server, socket, addr):
        self.server = server
        self.socket = socket
        self.addr = addr
        self.socket.setblocking(0)
        self.buf_size = 4096
        self.__verbose = True

        self.id = -1
        self.room_id = -1
        self.nickname = ""
        self.connected = True
        self.keep_running = True
        self.thread = threading.Thread(target=self.handle)
        self.thread.Daemon = True
        self.thread.start()

    def close(self):
        self.keep_running = False
        self.server.exit(self.id)
        self.broadcast_player_list(self.room_id)
        self.broadcast_spectator_list(self.room_id)
        self.broadcast_game(self.room_id)
        if self in self.server.handlers:
            self.server.handlers.remove(self)
        self.socket.close()

    def handle(self):
        while self.keep_running and self.server.keep_running:
            try:
                messages = list()
                while self.keep_running and self.server.keep_running:

                    # check socket if it is ready to read
                    socket_ready_to_read, _, _ = select.select(
                        [self.socket], [], [], 0.5)
                    if self.socket not in socket_ready_to_read:
                        continue

                    # receive the packet
                    message = self.socket.recv(self.buf_size).decode('utf-8')

                    # client is disconnected
                    if len(message) == 0:
                        self.__verbose and print(
                            "Client", str(self.addr),
                            "disconnected, exiting...")
                        self.close()
                        return

                    self.__verbose and print(
                        "Received", len(message), "bytes:", message.strip())
                    messages.append(message)

                    # keep recv until PROTOCOL_END is received
                    if message.endswith(protocol.PROTOCOL_END):
                        break

                self.recv("".join(messages))

            except select.error:
                pass

            except Exception as e:
                print("Exception:", str(e))

    def recv(self, message):
        try:
            message = message.split(protocol.PROTOCOL_END)
            for msg in message:
                if not msg:
                    continue

                # try to load as json, check if action is in message
                message = json.loads(msg)
                if protocol.ACTION not in message:
                    return

                # call responsible method
                action = message[protocol.ACTION]
                recv_action = getattr(self, "recv_" + action, None)
                if callable(recv_action):
                    recv_action(message)
                else:
                    self.__verbose and print("Not implemented action:", action)

        except ValueError:
            pass

        except KeyError:
            pass
