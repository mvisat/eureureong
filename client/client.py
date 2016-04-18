import socket

from client.handler import Handler


class Client:

    def __init__(self, host, port):
        self.verbose = True
        self.keep_running = True

        # connect to server host:port
        self.server_host = host
        self.server_port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.connect((self.server_host, self.server_port))
        self.server_socket.setblocking(0)

        # randomize client udp port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', 0))
        self.host, self.port = self.socket.getsockname()
        self.verbose and print(
            "Listening UDP at %s:%d" % (self.host, self.port))

        self.handler = Handler(self, self.server_socket, self.socket)

    # def send
