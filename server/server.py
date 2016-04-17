import operator
import threading

from common import protocol


class server:

    def __init__(self):
        self.handlers = []
        self.handlers_lock = threading.Lock()
        self.keep_running = True
