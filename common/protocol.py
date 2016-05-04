"""
Module containing protocol constants
"""

INVALID_ID = -1

PROTOCOL_START = "{"
PROTOCOL_END = "}"

METHOD = "method"
METHOD_JOIN = "join"
METHOD_LEAVE = "leave"
METHOD_READY = "ready"
METHOD_CLIENT_ADDRESS = "client_address"
METHOD_LEADER_ELECTION = "leader_election"
METHOD_PREPARE_PROPOSAL = "prepare_proposal"
METHOD_ACCEPT_PROPOSAL = "accept_proposal"
METHOD_ACCEPTED_PROPOSAL = "accepted_proposal"
METHOD_VOTE_WEREWOLF = "vote_werewolf"
METHOD_VOTE_RESULT_WEREWOLF = "vote_result_werewolf"
METHOD_VOTE_CIVILIAN = "vote_civilian"
METHOD_VOTE_RESULT_CIVILIAN = "vote_result_civilian"
METHOD_START = "start"
METHOD_CHANGE_PHASE = "change_phase"
METHOD_GAME_OVER = "game_over"
METHOD_VOTE_NOW = "vote_now"
METHOD_KPU_SELECTED = "kpu_selected"

STATUS = "status"
STATUS_OK = "ok"
STATUS_FAIL = "fail"
STATUS_ERROR = "error"

CLIENTS = "clients"
DESCRIPTION = "description"

PROPOSAL_ID = "proposal_id"
KPU_ID = "kpu_id"
KPU_PREV_ACCEPTED = "previous_accepted"

PLAYER_ID = "player_id"
PLAYER_IS_ALIVE = "is_alive"
PLAYER_ADDRESS = "address"
PLAYER_PORT = "port"
PLAYER_UDP_ADDRESS = "udp_address"
PLAYER_UDP_PORT = "udp_port"
PLAYER_USERNAME = "username"

VOTE_STATUS = "vote_status"
PLAYER_KILLED = "player_killed"
VOTE_RESULT = "vote_result"

PHASE = "phase"
TIME = "time"
TIME_DAY = "day"
TIME_NIGHT = "night"
ROLE = "role"
ROLE_WEREWOLF = "werewolf"
ROLE_CIVILIAN = "civilian"
FRIEND = "friend"
DAYS = "days"
WINNER = "winner"

DESC_WRONG_REQUEST = "Wrong request."
DESC_NOT_JOINED = "Kamu belum bergabung."
DESC_ALREADY_JOINED = "Kamu telah bergabung."
DESC_SERVER_IS_FULL = "Server telah penuh."
DESC_USERNAME_BLANK = "Nama tidak boleh kosong"
DESC_GAME_IS_PLAYING = "Permainan sedang berlangsung."
DESC_USERNAME_EXISTS = "Nama itu telah ada yang memakai."
DESC_WAIT_TO_START = "Menunggu pemain lain untuk memulai permainan..."
DESC_WERE_READY = "Kamu telah siap!"
DESC_GAME_START = """Pada suatu tempat, terdapat desa yang aman dan tentram. Warga desa tersebut sangatlah bahagia dengan kemakmuran dan kedamaian yang mereka.
Hingga suatu hari muncullah seseorang yang merubah segalanya. Kejahatan yang berada dalam kegelapan mendatangi mereka.

Siang ini, warga desa mengetahui kabar bahwa terdapat beberapa werewolf yang sedang bersembunyi ditengah desa mereka.
Untuk itu, warga desa melakukan pemilihan untuk membunuh orang yang diduga keras sebagai werewolf dalam penyamaran."""
DESC_CLIENT_LIST = "List of clients retrieved."
DESC_ACCEPTED = "accepted"
DESC_REJECTED = "rejected"
DESC_KPU_SELECTED = "KPU is selected."
DESC_KPU_ALREADY_SELECTED = "KPU telah terpilih."
