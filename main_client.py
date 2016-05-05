#!/usr/bin/python3

import argparse
import threading
import time
import signal
import json

from common import protocol
from client.client import Client


class Game(Client):
    def __init__(self, host, port, verbose=None):
        super().__init__(host, port, verbose)

        self.proposal_seq = 0
        self.accepted_count = 0
        self.previous_accepted_kpu_id = None
        self.last_accepted_proposal_id = [0, 0]

    def _do_as_proposer(self, proposer_candidates):
        while self.keep_running and self.server_state == protocol.METHOD_LEADER_ELECTION:
            self.proposal_seq += 1
            self.accepted_count = 0
            self.previous_accepted_kpu_id = self.player_id
            for client in self.clients:
                cid = client[protocol.PLAYER_ID]
                if cid == self.player_id:
                    continue
                address = client[protocol.PLAYER_ADDRESS]
                port = client[protocol.PLAYER_PORT]
                self.prepare_proposal((self.proposal_seq, self.player_id), (address, port))

            time.sleep(1)
            quorum = (len(self.clients) - 1) // 2 + 1

            if self.accepted_count < quorum:
                continue

            for client in self.clients:
                cid = client[protocol.PLAYER_ID]
                if cid in proposer_candidates:
                    continue
                address = client[protocol.PLAYER_ADDRESS]
                port = client[protocol.PLAYER_PORT]
                self.accept_proposal(
                    (self.proposal_seq, self.player_id),
                    self.previous_accepted_kpu_id, (address, port))

    def _leader_election(self):
        print()
        print("Kami sedang melakukan pemilihan ketua KPU. Tunggu sebentar...")
        proposer_candidates = [
            client[protocol.PLAYER_ID] for client in self.clients
        ]
        proposer_candidates.sort(reverse=True)
        proposer_candidates = proposer_candidates[:2]

        if self.player_id in proposer_candidates:
            proposer_thread = threading.Thread(target=self._do_as_proposer, args=(proposer_candidates,))
            proposer_thread.start()

    def _voting(self):
        self.client_address()
        time.sleep(1)
        for client in self.clients:
            if client[protocol.PLAYER_ID] == self.player_id:
                if not client[protocol.PLAYER_IS_ALIVE]:
                    if self.vote_number == 1:
                        print()
                        print("Kamu telah mati sehingga tidak dapat memilih. Tunggu pemain lain...")
                    return

        voting_time = self.game_time
        if voting_time == protocol.TIME_NIGHT and self.player_role == protocol.ROLE_CIVILIAN:
            if self.vote_number == 1:
                print()
                print("Kamu sedang tidur nyenyak...")
            return

        if self.vote_number > 1:
            print("Hmm, sepertinya pemilihan tadi tidak mencapai kesepakatan.")
        print()
        print("--- Pemilihan ke-%d ---" % (self.vote_number))
        print("Daftar pemain:")

        set_to_kill_id = set()
        for client in self.clients:
            eligible = True
            is_alive = client[protocol.PLAYER_IS_ALIVE]
            if not is_alive:
                eligible = False
                role = client[protocol.ROLE]

            cid = client[protocol.PLAYER_ID]
            is_werewolf = client[protocol.PLAYER_USERNAME] in self.friends
            if voting_time == protocol.TIME_NIGHT:
                if is_werewolf:
                    eligible = False
                elif cid == self.player_id:
                    eligible = False

            if eligible:
                set_to_kill_id.add(cid)

            str_player = " %s %d - %s" % ("✔" if eligible else "✘", cid, client[protocol.PLAYER_USERNAME])
            if not is_alive:
                str_player += " (%s terbunuh)" % (role)
            elif cid == self.player_id:
                str_player += " (kamu)"
            elif is_werewolf:
                str_player += " (teman)"
            print(str_player)

        while True:
            if not self.keep_running:
                return None
            try:
                print()
                kill_id = int(input("Masukkan ID pemain untuk dibunuh: "))
                if kill_id not in set_to_kill_id:
                    raise(ValueError)
                print("Kamu telah memilih! Tunggu pemain lain...")
                break
            except ValueError:
                print("Kamu salah memasukkan ID pemain, coba lagi!")

        if voting_time == protocol.TIME_DAY:
            self.vote_civilian(kill_id, (self.kpu_address, self.kpu_port))
        elif voting_time == protocol.TIME_NIGHT:
            self.vote_werewolf(kill_id, (self.kpu_address, self.kpu_port))

    def play(self):
        try:
            while self.keep_running:

                if not self.server_state or self.server_state == protocol.METHOD_JOIN:
                    if not self.is_joined:
                        player_name = None
                        while not player_name:
                            player_name = input("Masukkan namamu: ").strip()
                        self.join(player_name)
                    else:
                        self.player_name = player_name
                        print("Tekan tombol [Enter] jika kamu sudah siap!", end=' ')
                        input()
                        if not self.keep_running:
                            return
                        self.ready()

                elif self.server_state == protocol.METHOD_LEADER_ELECTION:
                    self._leader_election()

                elif self.server_state == protocol.METHOD_VOTE_NOW:
                    self._voting()

                if not self.keep_running or self.server_state == protocol.METHOD_GAME_OVER:
                    break

                with self.cv:
                    self.cv.wait()

        except KeyboardInterrupt:
            pass

        finally:
            self.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("host", type=str, help="server host")
    parser.add_argument("port", type=int, help="server port")
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    game = Game(args.host, args.port, args.verbose)
    game.play()

if __name__ == "__main__":
    main()
