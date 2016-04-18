import select


class Handler:

    def __init__(self, client):
        self.verbose = True
        self.keep_running = True

        self.client = client

    def handle(self):
        pass
