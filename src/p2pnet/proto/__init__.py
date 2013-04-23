from p2p_pb2 import *
from dht_pb2 import *

def applyFlag(cls, flag, filter_, flagAttr="flags"):
	def fget(self):
		return bool(getattr(self, flagAttr) & filter_)
	def fset(self, val):
		f = getattr(self, flagAttr)
		f = f ^ (filter_ & f) | (bool(val) * filter_)
		setattr(self, flagAttr, f)
	setattr(cls, flag, property(fget, fset))

def applyFlags(cls, flags, flagAttr="flags"):
	filter_ = 1
	for flag in flags:
		applyFlag(cls, flag, filter_, flagAttr)
		filter_ *= 2

applyFlags(Peer, ["reachable"])
applyFlags(PeerList, ["complete", "shouldReply"])
applyFlags(DHTRequest.Retrieve, ["includeMeta", "includeSubscribers"])
applyFlags(DHTEntry.Subscription, ["observeValues", "observeSubscribers", 
								   "observeTimeout", "observeProtection", "forwardData"])
applyFlags(DHTEntry.Protection, ["protectRetrieveValues", "protectRetrieveMeta",
								 "protectRetrieveSubscribers", "protectPublish",
								 "protectDelete", "protectSetTimeout", "protectSubscribe"])

from google.protobuf import text_format #@UnresolvedImport

def m2s(msg):
	return text_format.MessageToString(msg, as_one_line=True)
