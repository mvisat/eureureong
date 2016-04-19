"""
Module containing protocol constants
"""

INVALID_ID = -1

PROTOCOL_END = "}"

METHOD = "method"
METHOD_JOIN = "join"
METHOD_LEAVE = "leave"
METHOD_READY = "ready"
METHOD_CLIENT_ADDRESS = "client_address"
METHOD_PREPARE_PROPOSAL = "prepare_proposal"
METHOD_ACCEPT_PROPOSAL = "accept_proposal"
METHOD_VOTE_WEREWOLF = "vote_werewolf"
METHOD_VOTE_RESULT_WEREWOLF = "vote_result_werewolf"
METHOD_VOTE_CIVILIAN = "vote_civilian"
METHOD_VOTE_RESULT_CIVILIAN = "vote_result_civilian"
METHOD_START = "start"
METHOD_CHANGE_PHASE = "change_phase"
METHOD_GAME_OVER = "game_over"

STATUS = "status"
STATUS_OK = "ok"
STATUS_FAIL = "fail"
STATUS_ERROR = "error"
STATUS_ERROR_WRONG_REQ = "Wrong request"

CLIENTS = "clients"
DESCRIPTION = "description"

PROPOSAL_ID = "proposal_id"
PROPOSAL_PREV_ACCEPTED = "previous_accepted"
KPU_ID = "kpu_id"

PLAYER_ID = "player_id"
PLAYER_IS_ALIVE = "is_alive"
PLAYER_ADDRESS = "address"
PLAYER_PORT = "port"
PLAYER_USERNAME = "username"

VOTE_STATUS = "vote_status"
PLAYER_KILLED = "player_killed"
VOTE_RESULT = "vote_result"

TIME = "time"
TIME_DAY = "day"
TIME_NIGHT = "night"
ROLE = "role"
ROLE_WEREWOLF = "werewolf"
ROLE_CIVILIAN = "civilian"
FRIEND = "friend"
DAYS = "days"
WINNER = "winner"

DESC_NOT_JOINED = "You are not joined."
DESC_ALREADY_JOINED = "You are already joined."
DESC_SERVER_IS_FULL = "Server is full."
DESC_USERNAME_BLANK = "Username can't be blank."
DESC_GAME_IS_PLAYING = "Game is currently running."
DESC_USERNAME_EXISTS = "Username already exists."
DESC_WAIT_TO_START = "Waiting for other players to start."
DESC_WERE_READY = "You were ready."
DESC_GAME_START = "Game is started."
DESC_CLIENT_LIST = "List of clients retrieved."
