import select


class Handler:

    def __init__(self, client, server_socket, socket):
        self.verbose = True
        self.keep_running = True

        self.client = client
        self.server_socket = server_socket
        self.socket = socket
        self.buf_size = 1024

    def close(self):
        self.keep_running = False
        self.client.keep_running = False
        self.server_socket.close()
        self.socket.close()

    def recv_server(self):
        while self.keep_running and self.client.keep_running:
            try:
                readable, _, _ = select.select([self.server_socket], [], [], 0.5)
                if self.server_socket not in readable:
                    continue

                data = self.server_socket.recv(self.buf_size)

                # server disconnected
                if not data:
                    self.close()
                    break

                self.verbose and print("recv_server:", data)

            except select.error:
                self.close()

    def recv(self):
        while self.keep_running and self.client.keep_running:
            try:
                readable, _, _ = select.select([self.socket], [], [], 0.5)
                if self.socket not in readable:
                    continue

                data, address = self.socket.recvfrom(self.buf_size)

                # server disconnected
                if not data:
                    self.close()
                    break

                self.verbose and print("recv from", address, ":", data)

            except select.error as e:
                self.close()
