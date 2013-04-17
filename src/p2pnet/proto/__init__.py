from p2p_pb2 import *
from dht_pb2 import *

from google.protobuf import text_format #@UnresolvedImport

def m2s(msg):
	return text_format.MessageToString(msg, as_one_line=True)
