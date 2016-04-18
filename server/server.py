import socket
import select
import threading

from common import protocol
from server.handler import Handler


class Server:

    def __init__(self, host='', port=9999):
        self.verbose = True
        self.keep_running = True
        self.buf_size = 2048
        self.timeout = 1

        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(6)

        self.handler = Handler(self)
        self.lock = threading.Lock()
        self.client_sockets = []
        self.client_addrs = []
        self.threads = []

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

                thread = threading.Thread(
                    target=self._recv, args=(client_socket, client_addr))
                self.threads.append(thread)
                thread.start()

        except KeyboardInterrupt:
            self.verbose and print("Terminated by user")

        finally:
            self.keep_running = False
            for thread in self.threads:
                thread.join()
            self.socket.close()

    def close(self):
        self.keep_running = False

    def _recv(self, client_socket, client_addr):
        messages = []
        while self.keep_running:
            try:
                # check socket if it is ready to read
                readable, _, _ = select.select([client_socket], [], [], self.timeout)
                if client_socket not in readable:
                    continue

                # receive the packet
                message = client_socket.recv(self.buf_size)

                # client is disconnected
                if not message:
                    self.verbose and print(
                        "Client", str(client_addr),
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
                with self.lock:
                    self.handler.handle(client_socket, full_message)
                messages.clear()

            except select.error:
                break

            except Exception as e:
                print(e)
                break

        client_socket.close()

    def _send(self, client_socket, message):
        if isinstance(message, bytes):
            pass
        else:
            if not isinstance(message, str):
                message = str(message)
            message = message.encode()

        total_sent = 0
        while self.keep_running and total_sent < len(message):
            _, writable, _ = select.select([], [client_socket], [], self.timeout)
            if client_socket not in writable:
                continue

            print("Sending:", message)
            sent = client_socket.send(message[total_sent:])
            if sent == 0:
                break
            total_sent += sent
