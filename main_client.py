#!/usr/bin/python3

import argparse
import threading
import time
import signal
import json

from common import protocol
from client.client import Client


class Game(Client):
    TIMEOUT = 15
    def __init__(self, host, port, verbose=None):
        super().__init__(host, port, verbose)
        self.proposal_seq = 0
        self.last_accepted_proposal_id = [0, 0]
        self.previous_accepted_kpu_id = None

    def _do_as_proposer(self, proposer_candidates, waiting_time=1):
        while self.keep_running:
            time.sleep(waiting_time)

            # check if consensus has been reached
            vote_now = self.server_recv(timeout=0)
            if vote_now:
                method = vote_now[protocol.METHOD]
                if (method != protocol.METHOD_VOTE_NOW and
                        method != protocol.METHOD_KPU_SELECTED):
                    continue
                self.kpu_id = vote_now[protocol.KPU_ID]
                for client in self.clients:
                    if client[protocol.PLAYER_ID] == self.kpu_id:
                        self.kpu_address = client[protocol.PLAYER_ADDRESS]
                        self.kpu_port = client[protocol.PLAYER_PORT]
                        return
                assert(True)

            self.proposal_seq += 1
            for client in self.clients:
                cid = client[protocol.PLAYER_ID]
                if cid in proposer_candidates:
                    continue
                address = client[protocol.PLAYER_ADDRESS]
                port = client[protocol.PLAYER_PORT]
                self.prepare_proposal((self.proposal_seq, self.player_id), (address, port))

            acceptor_responses = set()
            self.previous_accepted_kpu_id = self.player_id
            quorum = (len(self.clients) - 2) // 2 + 1
            last_time = time.time()
            while len(acceptor_responses) < quorum:
                time.sleep(self.poll_time)
                if time.time() - last_time >= Game.TIMEOUT:
                    break
                acceptor_response = self.recv(timeout=0)
                if not acceptor_response:
                    continue
                acceptor, response = acceptor_response

                # acceptor replies
                if acceptor not in acceptor_responses:
                    status = response[protocol.STATUS]
                    if status == protocol.STATUS_OK:
                        acceptor_responses.add(acceptor)
                        if protocol.KPU_PREV_ACCEPTED not in response:
                            continue
                        self.previous_accepted_kpu_id = response[protocol.KPU_PREV_ACCEPTED]

            if len(acceptor_responses) < quorum:
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

            time.sleep(waiting_time)
            while self.recv(timeout=0):
                pass

    def _do_as_acceptor(self, waiting_time=1):
        while self.keep_running:
            time.sleep(waiting_time)

            # check if consensus has been reached
            vote_now = self.server_recv(timeout=0)
            if vote_now:
                method = vote_now[protocol.METHOD]
                if (method != protocol.METHOD_VOTE_NOW and
                        method != protocol.METHOD_KPU_SELECTED):
                    continue
                self.kpu_id = vote_now[protocol.KPU_ID]
                for client in self.clients:
                    if client[protocol.PLAYER_ID] == self.kpu_id:
                        self.kpu_address = client[protocol.PLAYER_ADDRESS]
                        self.kpu_port = client[protocol.PLAYER_PORT]
                        return
                assert(True)

            address_proposal = self.recv(timeout=0)
            if address_proposal:
                address, proposal = address_proposal
                method = proposal[protocol.METHOD]
                if method  == protocol.METHOD_PREPARE_PROPOSAL:
                    proposal_id = proposal[protocol.PROPOSAL_ID]
                    accepted = proposal_id >= self.last_accepted_proposal_id
                    if accepted:
                        data = {
                            protocol.STATUS: protocol.STATUS_OK,
                            protocol.DESCRIPTION: protocol.DESC_ACCEPTED,
                        }
                        if self.previous_accepted_kpu_id is not None:
                            data[protocol.KPU_PREV_ACCEPTED] = self.previous_accepted_kpu_id
                        self.last_accepted_proposal_id = proposal_id
                    else:
                        data = {
                            protocol.STATUS: protocol.STATUS_FAIL,
                            protocol.DESCRIPTION: protocol.DESC_REJECTED
                        }
                    self.connection.send(json.dumps(data), address, unreliable=True)

                elif method == protocol.METHOD_ACCEPT_PROPOSAL:
                    proposal_id = proposal[protocol.PROPOSAL_ID]
                    accepted = proposal_id >= self.last_accepted_proposal_id
                    if accepted:
                        data = json.dumps({
                            protocol.STATUS: protocol.STATUS_OK,
                            protocol.DESCRIPTION: protocol.DESC_ACCEPTED
                        })
                    else:
                        data = json.dumps({
                            protocol.STATUS: protocol.STATUS_FAIL,
                            protocol.DESCRIPTION: protocol.DESC_REJECTED
                        })
                    self.connection.send(data, address, unreliable=True)

                    if accepted:
                        # send to learner
                        kpu_id = proposal[protocol.KPU_ID]
                        data = json.dumps({
                            protocol.METHOD: protocol.METHOD_ACCEPT_PROPOSAL,
                            protocol.KPU_ID: kpu_id,
                            protocol.DESCRIPTION: protocol.DESC_KPU_SELECTED
                        })
                        self.connection.server_send(data)

    def _leader_election(self):
        print("We now have leader election. Please wait...")
        proposer_candidates = [
            client[protocol.PLAYER_ID] for client in self.clients
        ]
        proposer_candidates.sort(reverse=True)
        proposer_candidates = proposer_candidates[:2]

        if self.player_id in proposer_candidates:
            self._do_as_proposer(proposer_candidates)
        else:
            self._do_as_acceptor()

    def _voting(self, voting_time):
        dead_werewolf = 0
        alive_player = 0
        for client in self.clients:
            is_alive = client[protocol.PLAYER_IS_ALIVE]
            if client[protocol.PLAYER_ID] == self.player_id:
                im_alive = is_alive
            if is_alive:
                alive_player += 1
            elif client[protocol.ROLE] == protocol.ROLE_WEREWOLF:
                dead_werewolf += 1

        if voting_time == protocol.TIME_DAY:
            quorum = alive_player
        elif voting_time == protocol.TIME_NIGHT:
            quorum = 2 - dead_werewolf

        vote_number = 0
        while True:
            vote_number += 1
            # workaround, ignore vote_now
            if vote_number == 1 and voting_time == protocol.TIME_NIGHT:
                pass
            else:
                ret = self.server_recv()
                if not ret:
                    return None
                elif protocol.METHOD not in ret:
                    return None
                method = ret[protocol.METHOD]
                if (method == protocol.METHOD_CHANGE_PHASE or
                        method == protocol.METHOD_GAME_OVER):
                    return ret
                assert(method == protocol.METHOD_VOTE_NOW)

            # dead player can't vote
            if not im_alive:
                if vote_number == 1:
                    print("You're dead, so you can't vote")
            # civilian is sleeping at night
            elif voting_time == protocol.TIME_NIGHT and self.player_role == protocol.ROLE_CIVILIAN:
                if vote_number == 1:
                    print("You're sleeping tight...")
            else:
                print("Vote #%d" % (vote_number))
                if voting_time == protocol.TIME_DAY:
                    print("Available players:")
                else:
                    print("Available civilians:")

                set_to_kill_id = set()
                for client in self.clients:
                    is_alive = client[protocol.PLAYER_IS_ALIVE]
                    if not is_alive:
                        continue

                    cid = client[protocol.PLAYER_ID]
                    is_werewolf = client[protocol.PLAYER_USERNAME] in self.player_friends
                    if voting_time == protocol.TIME_NIGHT:
                        if is_werewolf:
                            continue
                        elif cid == self.player_id:
                            continue

                    set_to_kill_id.add(cid)
                    print("%d. %s" % (cid, client[protocol.PLAYER_USERNAME]))

                while True:
                    if not self.keep_running:
                        return None
                    try:
                        kill_id = int(input("Select player ID to kill: "))
                        if kill_id not in set_to_kill_id:
                            raise(ValueError)
                        break
                    except ValueError:
                        print("Invalid player ID.")

                if voting_time == protocol.TIME_DAY:
                    self.vote_civilian(kill_id, (self.kpu_address, self.kpu_port))
                elif voting_time == protocol.TIME_NIGHT:
                    self.vote_werewolf(kill_id, (self.kpu_address, self.kpu_port))

            if self.kpu_id == self.player_id:
                vote_count = {}
                count = 0
                while count < quorum:
                    address_kill = self.recv()
                    address, kill = address_kill
                    if protocol.METHOD not in kill:
                        continue

                    if voting_time == protocol.TIME_DAY:
                        method_vote = protocol.METHOD_VOTE_CIVILIAN
                    elif voting_time == protocol.TIME_NIGHT:
                        method_vote = protocol.METHOD_VOTE_WEREWOLF
                    if kill[protocol.METHOD] != method_vote:
                        continue

                    kill_id = kill[protocol.PLAYER_ID]
                    if kill_id not in vote_count:
                        vote_count[kill_id] = 1
                    else:
                        vote_count[kill_id] += 1
                    count += 1

                vote_max = 0
                player_killed = None
                for kill_id, vote in vote_count.items():
                    if vote > vote_max:
                        vote_max = vote
                        player_killed = kill_id
                    elif vote == vote_max:
                        player_killed = None

                if player_killed is None:
                    if voting_time == protocol.TIME_DAY:
                        self.vote_result_civilian(-1, vote_count)
                    else:
                        self.vote_result_werewolf(-1, vote_count)
                else:
                    if voting_time == protocol.TIME_DAY:
                        self.vote_result_civilian(1, vote_count, player_killed)
                    else:
                        self.vote_result_werewolf(1, vote_count, player_killed)

    def play(self):
        try:
            # ask username and join the server
            while self.keep_running:
                username = input("Enter your username: ").strip()
                if not username:
                    continue

                ret = self.join(username)
                if ret[protocol.STATUS] == protocol.STATUS_OK:
                    self.player_id = ret[protocol.PLAYER_ID]
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
            ret[protocol.DAYS] = 1

            print(ret[protocol.DESCRIPTION])
            self.player_role = ret[protocol.ROLE]
            print("You are a", self.player_role)
            if self.player_role == protocol.ROLE_WEREWOLF:
                self.player_friends = ret[protocol.FRIEND]
                print("Your friends:", self.player_friends)
            else:
                self.player_friends = []

            last_clients = None
            while True:
                if not self.keep_running:
                    return

                self.clients = self.client_address()[protocol.CLIENTS]
                if last_clients is not None:
                    if len(last_clients) == len(self.clients):
                        for i in range(len(self.clients)):
                            if self.clients[i] != last_clients[i]:
                                role = self.clients[i][protocol.ROLE]
                                username = self.clients[i][protocol.PLAYER_USERNAME]
                                print("A %s named %s has been killed!" % (role, username))
                last_clients = self.clients

                if ret[protocol.METHOD] == protocol.METHOD_GAME_OVER:
                    break

                print("Day: %d, Time: %s" % (ret[protocol.DAYS], ret[protocol.TIME]))

                time_now = ret[protocol.TIME]
                if time_now  == protocol.TIME_DAY:
                    self._leader_election()
                    ret = self._voting(time_now)
                elif time_now == protocol.TIME_NIGHT:
                    ret = self._voting(time_now)

                if not ret:
                    return
                elif ret[protocol.METHOD] == protocol.METHOD_GAME_OVER:
                    pass
                # workaround, ignore vote_now
                elif time_now == protocol.TIME_DAY:
                    self.server_recv()

            print("Game over!", ret[protocol.DESCRIPTION])

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
