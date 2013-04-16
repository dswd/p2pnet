import logging

from ..base import Event
from .. import proto

logger = logging.getLogger(__name__)

Event.TYPE_DHT_REPLY = "dht_reply"
Event.TYPE_DHT_EVENT = "dht_event"

class Entry:
	def __init__(self, hash, key):
		self.hash = hash
		self.key = key
		self.values = []
	def handle(self, request):
		if request.HasField("retrieve"):
			pass
		elif request.HasField("publish"):
			pos = request.publish.storeAt
			self.values = self.values[:pos] + request.publish.values + self.values[pos:]
			return proto.DHTReply(status=proto.DHTReply.SUCCESS) #@UndefinedVariable
		elif request.HasField("delete"):
			pass
		elif request.HasField("setTimeout"):
			pass
		elif request.HasField("subscribe"):
			pass
		elif request.HasField("protect"):
			pass
		else:
			return proto.DHTReply(status=proto.DHTReply.ERROR, errorCode=proto.DHTReply.REQUEST_INVALID) #@UndefinedVariable

class Feature:
	def __init__(self, node):
		self.node = node
		self.handles = {}
		node.addListener(self._handleRoutedMessage, Event.TYPE_MESSAGE_ROUTED)
		node.addListener(self._handlePeerListChanged, Event.TYPE_PEERLIST_CHANGED)
		node.features[__name__] = self
		self.entries = {}
	def _handleRequest(self, key, request):
		if not key in self.entries:
			return proto.DHTReply(status=proto.DHTReply.ERROR, errorCode=proto.DHTReply.ENTRY_UNKNOWN) #@UndefinedVariable
		return self.entries[key].handle(request)
	def _handleDhtMessage(self, rmsg, dhtmsg):
		if dhtmsg.type == proto.DHTMessage.REPLY: #@UndefinedVariable
			self.node._event(type=Event.TYPE_DHT_REPLY, data=dhtmsg) #@UndefinedVariable
		elif dhtmsg.type == proto.DHTMessage.EVENT: #@UndefinedVariable
			self.node._event(type=Event.TYPE_DHT_EVENT, data=dhtmsg) #@UndefinedVariable
		elif dhtmsg.type == proto.DHTMessage.REQUEST: #@UndefinedVariable
			reply = proto.DHTMessage(type=proto.DHTMessage.REPLY, hash=dhtmsg.hash, key=dhtmsg.key) #@UndefinedVariable
			aborted = False
			for req in dhtmsg.request:
				if not aborted:
					r = self._handleRequest(dhtmsg.key, req)
				else:
					r = proto.DHTReply(status=proto.DHTReply.SKIPPED) #@UndefinedVariable
				if r.status == proto.DHTReply.ERROR and dhtmsg.abortOnError: #@UndefinedVariable
					aborted = True
				reply.reply.add(r)
			self.node.reply(rmsg, dhtmsg=[reply])
	def _handleRoutedMessage(self, evt):
		msg = evt.getData()
		for dhtMsg in msg.dhtMsg:
			self._handleDhtMessage(msg, dhtMsg)
	def _handlePeerListChanged(self, evt):
		peers = evt.getData()
		#TODO: check if some data belongs to neighbors