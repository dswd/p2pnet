from proto import p2p_pb2 as proto

INITIALIZATION_MESSAGE = proto.Initialization(magic="p2pnet", minVersion=0, maxVersion=0)

MAX_ID = 1<<64 #default: 1<<64

MAX_SHORT = 6 #default: 6
MAX_LONG = 60 #default: 60
MAX_TRAFFIC = 10

MAX_MESSAGE_SIZE = 1<<20

PEER_LIST_INTERVAL = 60 #default: 60
CLEANUP_INTERVAL = 60 #default: 60

CONNECTION_TIMEOUT = 120 #default: 120

DEFAULT_TTL = 128
MAX_TTL = 1024

TRAFFIC_AVERAGING = 60 # half-life-time for traffic in seconds

MAX_DHT_TIMEOUT = 60 * 60 * 24 * 14 #14 days
MAX_DHT_PROTECTION_TIMEOUT = 60 * 60 * 24 * 14 #14 days
MAX_DHT_SUBSCRIPTION_TIMEOUT = 60 * 60 * 24 * 14 #14 days
