from proto import p2p_pb2 as proto

INITIALIZATION_MESSAGE = proto.Initialization(magic="p2pnet", minVersion=0, maxVersion=0)

MAX_ID = 1<<10 #default: 1<<64

MAX_SHORT = 2 #default: 6
MAX_LONG = 2 #default: 60
MAX_TRAFFIC = 10

PEER_LIST_INTERVAL = 10 #default: 60
CLEANUP_INTERVAL = 10 #default: 60

CONNECTION_TIMEOUT = 60 #default: 120

DEFAULT_TTL = 32
MAX_TTL = 64