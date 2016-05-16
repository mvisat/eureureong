import threading

from common import protocol


class Handler:

    def __init__(self, client):
        self.client = client

        self.client.player_id = None
        self.client.clients = None
        self.client.is_joined = False

        self.client.state = None
        self.client.server_state = None

        self.is_leader_election = False
        self.handler_lock = threading.Lock()

    def handle(self, message, address):
        with self.handler_lock:
            if protocol.STATUS in message:
                status = message[protocol.STATUS]
                state = self.client.state

                if state == protocol.METHOD_PREPARE_PROPOSAL:
                    if status == protocol.STATUS_OK:
                        self.client.accepted_count += 1
                        if protocol.KPU_PREV_ACCEPTED in message:
                            self.client.previous_accepted_kpu_id = message[protocol.KPU_PREV_ACCEPTED]

            elif protocol.METHOD in message:
                method = message[protocol.METHOD]
                self.client.state = method

                if method == protocol.METHOD_PREPARE_PROPOSAL:
                    if protocol.PROPOSAL_ID in message:
                        proposal_id = message[protocol.PROPOSAL_ID]
                        accepted = proposal_id >= self.client.last_accepted_proposal_id
                        if accepted:
                            self.client.prepare_proposal_accept(proposal_id, self.client.previous_accepted_kpu_id, address)
                            self.client.last_accepted_proposal_id = proposal_id
                        else:
                            self.client.prepare_proposal_reject(proposal_id, address)

                elif method == protocol.METHOD_ACCEPT_PROPOSAL:
                    if protocol.PROPOSAL_ID in message:
                        proposal_id = message[protocol.PROPOSAL_ID]
                        accepted = proposal_id >= self.client.last_accepted_proposal_id
                        if accepted:
                            if protocol.KPU_ID in message:
                                kpu_id = message[protocol.KPU_ID]
                                self.client.accept_proposal_accept(kpu_id, address)
                        else:
                            self.client.accept_proposal_reject(address)

                elif method == protocol.METHOD_VOTE_CIVILIAN or method == protocol.METHOD_VOTE_WEREWOLF:
                    voting_time = self.client.game_time
                    if voting_time == protocol.TIME_DAY and method != protocol.METHOD_VOTE_CIVILIAN:
                        return
                    elif voting_time == protocol.TIME_NIGHT and method != protocol.METHOD_VOTE_WEREWOLF:
                        return

                    if protocol.PLAYER_ID in message:
                        dead_werewolf = 0
                        alive_player = 0
                        for client in self.client.clients:
                            is_alive = client[protocol.PLAYER_IS_ALIVE]
                            if is_alive:
                                alive_player += 1
                            elif client[protocol.ROLE] == protocol.ROLE_WEREWOLF:
                                dead_werewolf += 1

                        if voting_time == protocol.TIME_DAY:
                            quorum = alive_player
                        elif voting_time == protocol.TIME_NIGHT:
                            quorum = 2 - dead_werewolf

                        kill_id = message[protocol.PLAYER_ID]
                        if kill_id not in self.vote_count:
                            self.vote_count[kill_id] = set([address])
                        else:
                            self.vote_count[kill_id].add(address)

                        count = 0
                        vote_max = 0
                        player_killed = None
                        vote_array = []
                        for kill_id, voters in self.vote_count.items():
                            vote = len(voters)
                            count += vote
                            if vote >= (quorum//2+1):
                                player_killed = kill_id
                            vote_array.append([kill_id, vote])

                        if count >= quorum:
                            if player_killed is None:
                                if voting_time == protocol.TIME_DAY:
                                    self.client.vote_result_civilian(-1, vote_array)
                                else:
                                    self.client.vote_result_werewolf(-1, vote_array)
                            else:
                                if voting_time == protocol.TIME_DAY:
                                    self.client.vote_result_civilian(1, vote_array, player_killed)
                                else:
                                    self.client.vote_result_werewolf(1, vote_array, player_killed)
                            self.vote_count = {}

    def server_handle(self, message):
        with self.handler_lock:
            if protocol.STATUS in message:
                status = message[protocol.STATUS]
                server_state = self.client.server_state

                if server_state == protocol.METHOD_JOIN:
                    if status == protocol.STATUS_OK:
                        if protocol.PLAYER_ID in message:
                            self.client.is_joined = True
                            self.client.player_id = message[protocol.PLAYER_ID]
                    else:
                        if protocol.DESCRIPTION in message:
                            print(message[protocol.DESCRIPTION])
                    with self.client.cv:
                        self.client.cv.notify_all()

                elif server_state == protocol.METHOD_LEAVE:
                    pass

                elif server_state == protocol.METHOD_READY:
                    if protocol.DESCRIPTION in message:
                        print(message[protocol.DESCRIPTION])

                elif server_state == protocol.METHOD_CLIENT_ADDRESS:
                    if status == protocol.STATUS_OK:
                        if protocol.CLIENTS in message:
                            self.client.clients = message[protocol.CLIENTS]

                            if self.is_leader_election:
                                self.is_leader_election = False
                                self.client.server_state = protocol.METHOD_LEADER_ELECTION
                                with self.client.cv:
                                    self.client.cv.notify_all()

            elif protocol.METHOD in message:
                method = message[protocol.METHOD]
                self.client.server_state = method

                if method == protocol.METHOD_START:
                    self.client.game_day = 1

                    if protocol.ROLE in message:
                        role = message[protocol.ROLE]
                        self.client.player_role = role
                        print()
                        print("--- EUREUREONG | THE WEREWOLVES ---")
                        print("Hai %s!" % (self.client.player_name))
                        print("Tugasmu adalah menjadi: %s." % (role))

                    if protocol.FRIEND in message:
                        self.client.friends = message[protocol.FRIEND]
                        print("Temanmu: %s" % (self.client.friends))
                    else:
                        self.client.friends = []

                    if protocol.TIME in message:
                        self.client.game_time = message[protocol.TIME]
                        print()
                        print("Hari ke-%d, Waktu: %s" % (self.client.game_day, self.client.game_time))

                    if protocol.DESCRIPTION in message:
                        print(message[protocol.DESCRIPTION])

                    self.is_leader_election = True
                    self.client.client_address()

                    self.client.vote_number = 0

                elif method == protocol.METHOD_CHANGE_PHASE:
                    if protocol.TIME in message:
                        self.client.game_time = message[protocol.TIME]

                    if protocol.DAYS in message:
                        self.client.game_day = message[protocol.DAYS]

                    print()
                    print("Hari ke-%d, Waktu: %s" % (self.client.game_day, self.client.game_time))
                    if protocol.DESCRIPTION in message:
                        print(message[protocol.DESCRIPTION])

                    if self.client.game_time == protocol.TIME_DAY:
                        self.is_leader_election = True
                    self.client.client_address()

                    self.client.vote_number = 0

                elif method == protocol.METHOD_KPU_SELECTED:
                    if protocol.KPU_ID in message:
                        self.client.kpu_id = message[protocol.KPU_ID]
                        for client in self.client.clients:
                            if client[protocol.PLAYER_ID] == self.client.kpu_id:
                                print("Pemain '%s' terpilih menjadi ketua KPU!" % (client[protocol.PLAYER_USERNAME]))
                                self.client.kpu_address = client[protocol.PLAYER_ADDRESS]
                                self.client.kpu_port = client[protocol.PLAYER_PORT]
                                break

                elif method == protocol.METHOD_VOTE_NOW:
                    self.client.vote_number += 1
                    self.vote_count = {}
                    with self.client.cv:
                        self.client.cv.notify_all()

                elif method == protocol.METHOD_GAME_OVER:
                    if protocol.DESCRIPTION in message:
                        print()
                        print(message[protocol.DESCRIPTION])

                    with self.client.cv:
                        self.client.cv.notify_all()
