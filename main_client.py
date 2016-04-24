#!/usr/bin/python3

import argparse
import threading
import time
import signal

from common import protocol
from client.client import Client


class Game(Client):
    def __init__(self, host, port):
        super().__init__(host, port)

    def play(self):
        try:
            # ask username and join the server
            while self.keep_running:
                username = input("Enter your username: ").strip()
                if not username:
                    continue

                ret = self.join(username)
                if ret[protocol.STATUS] == protocol.STATUS_OK:
                    player_id = ret[protocol.PLAYER_ID]
                    break

                print(ret[protocol.DESCRIPTION])
            if not self.keep_running:
                return

            # get ready
            print("Press [Enter] if you are ready!", end=' ')
            input()
            if not self.keep_running:
                return
            ret = self.ready()
            if protocol.DESCRIPTION in ret:
                print(ret[protocol.DESCRIPTION])

            # wait until game is started
            ret = self.server_recv()
            if not self.keep_running:
                return
            print(ret[protocol.DESCRIPTION])
            role = ret[protocol.ROLE]
            print("You are a", role)
            if role == protocol.ROLE_WEREWOLF:
                print("Your friends:", ret[protocol.FRIEND])

            proposal_id = 0
            while True:
                # change phase
                ret = self.server_recv()
                if not self.keep_running:
                    return
                print("Day: %d, Time: %s" % (ret[protocol.DAYS], ret[protocol.TIME]))

                # stub for leader election
                # leader is client with player id = 0
                if player_id == 0:
                    proposal_id += 1
                    ret = self.client_address()
                    for client in ret[protocol.CLIENTS]:
                        if player_id == client[protocol.PLAYER_ID]:
                            continue
                        addr = client[protocol.PLAYER_ADDRESS]
                        port = client[protocol.PLAYER_PORT]
                        self.prepare_proposal(proposal_id, (addr, port))
                else:
                    ret = self.recv()
                    if not self.keep_running:
                        return
                    print(ret)

        except KeyboardInterrupt:
            pass

        except Exception as e:
            print("Exception:", e)

        finally:
            self.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("host", type=str, help="server host")
    parser.add_argument("port", type=int, help="server port")
    args = parser.parse_args()

    game = Game(args.host, args.port)
    game.play()

if __name__ == "__main__":
    main()
