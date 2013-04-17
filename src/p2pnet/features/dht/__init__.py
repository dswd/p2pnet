import logging, hashlib, struct

from ...base import Event
from ... import proto, config

import storage

logger = logging.getLogger(__name__)

Event.TYPE_DHT_REPLY = "dht_reply"
Event.TYPE_DHT_EVENT = "dht_event"

class Feature:
	def __init__(self, node):
		self.node = node
		node.addListener(self._handleRoutedMessage, Event.TYPE_MESSAGE_ROUTED)
		node.addListener(self._handlePeerListChanged, Event.TYPE_PEERLIST_CHANGED)
		node.features[__name__] = self
		self.entries = storage.Registry()
	def _handleRequest(self, dhtmsg, entry, request):
		if not entry:
			if request.HasField("publish"):
				entry = self.entries.createEntry(dhtmsg.hash, dhtmsg.key)
			else:
				return proto.DHTReply(status=proto.DHTReply.ERROR, errorCode=proto.DHTReply.ENTRY_UNKNOWN) #@UndefinedVariable
		if request.HasField("retrieve"):
			return self._handleRequestRetrieve(dhtmsg, entry, request.retrieve)
		elif request.HasField("publish"):
			return self._handleRequestPublish(dhtmsg, entry, request.publish)
		elif request.HasField("delete"):
			return self._handleRequestDelete(dhtmsg, entry, request.delete)
		elif request.HasField("setTimeout"):
			return self._handleRequestSetTimeout(dhtmsg, entry, request.setTimeout)
		elif request.HasField("subscribe"):
			return self._handleRequestSubscribe(dhtmsg, entry, request.subscribe)
		elif request.HasField("protect"):
			return self._handleRequestProtect(dhtmsg, entry, request.protect)
		else:
			return proto.DHTReply(status=proto.DHTReply.ERROR, errorCode=proto.DHTReply.REQUEST_INVALID) #@UndefinedVariable
	def _handleRequestRetrieve(self, dhtmsg, entry, retrieve):
		if retrieve.HasField("indexes") and (retrieve.HasField("firstIndex") or retrieve.HasField("lastIndex")):
			return proto.DHTReply(status=proto.DHTReply.ERROR, errorCode=proto.ErrorCode.REQUEST_INVALID, errorMsg="indexes must not be set when firstIndex or lastIndex is set") #@UndefinedVariable
		if retrieve.HasField("firstIndex") or retrieve.HasField("lastIndex"):
			values = entry.getValuesByRange(retrieve.firstIndex, retrieve.lastIndex)
		else:
			values = entry.getValuesByIndex(retrieve.indexes)
		entry = proto.DHTEntry(value=values)
		return proto.DHTReply(status=proto.DHTReply.SUCCESS, entry=entry) #@UndefinedVariable
	def _handleRequestPublish(self, dhtmsg, entry, publish):
		#TODO: fire subscription
		entry.addValues(publish.storeAt, publish.values)
		return proto.DHTReply(status=proto.DHTReply.SUCCESS) #@UndefinedVariable
	def _handleRequestDelete(self, dhtmsg, entry, delete):
		if delete.HasField("indexes") and (delete.HasField("firstIndex") or delete.HasField("lastIndex")):
			return proto.DHTReply(status=proto.DHTReply.ERROR, errorCode=proto.ErrorCode.REQUEST_INVALID, errorMsg="indexes must not be set when firstIndex or lastIndex is set") #@UndefinedVariable
		if delete.HasField("firstIndex") or delete.HasField("lastIndex"):
			entry.delValuesByRange(delete.firstIndex, delete.lastIndex)
		else:
			entry.delValuesByIndex(delete.indexes)
		return proto.DHTReply(status=proto.DHTReply.SUCCESS) #@UndefinedVariable
	def _handleRequestSetTimeout(self, dhtmsg, entry, setTimeout):
		#TODO: implement
		pass
	def _handleRequestSubscribe(self, dhtmsg, entry, subscribe):
		#TODO: implement
		pass
	def _handleRequestProtect(self, dhtmsg, entry, protect):
		#TODO: implement
		pass
	def _handleDhtMessage(self, rmsg, dhtmsg):
		if dhtmsg.type == proto.DHTMessage.REPLY: #@UndefinedVariable
			self.node._event(type=Event.TYPE_DHT_REPLY, data=dhtmsg) #@UndefinedVariable
		elif dhtmsg.type == proto.DHTMessage.EVENT: #@UndefinedVariable
			self.node._event(type=Event.TYPE_DHT_EVENT, data=dhtmsg) #@UndefinedVariable
		elif dhtmsg.type == proto.DHTMessage.REQUEST: #@UndefinedVariable
			entry = self.entries.getEntry(dhtmsg.hash, dhtmsg.key)
			aborted = False
			replies = []
			for req in dhtmsg.request:
				#FIXME: Implement protection
				if not aborted:
					r = self._handleRequest(dhtmsg, entry, req)
				else:
					r = proto.DHTReply(status=proto.DHTReply.SKIPPED) #@UndefinedVariable
				if r.status == proto.DHTReply.ERROR and dhtmsg.abortOnError: #@UndefinedVariable
					aborted = True
				replies.append(r)
			self.node._reply(rmsg, dhtMsg=[proto.DHTMessage(type=proto.DHTMessage.REPLY, hash=dhtmsg.hash, key=dhtmsg.key, reply=replies)]) #@UndefinedVariable
	def _handleRoutedMessage(self, evt):
		msg = evt.getData()
		for dhtMsg in msg.dhtMsg:
			self._handleDhtMessage(msg, dhtMsg)
	def _handlePeerListChanged(self, evt):
		peers = evt.getData()
		#TODO: check if some data belongs to neighbors

	def publish(self, key, values, **kwargs):
		pub = proto.DHTRequest.Publish(values=values, **kwargs)
		self.send(key=key, request=[self.createRequest(publish=pub)])
	def retrieve(self, key, **kwargs):
		retr = proto.DHTRequest.Retrieve(**kwargs)
		self.send(key=key, request=[self.createRequest(retrieve=retr)])
	def send(self, key, hash=None, type=proto.DHTMessage.REQUEST, **kwargs): #@ReservedAssignment, @UndefinedVariable
		if hash is None:
			hash = self.createHash(key) #@ReservedAssignment
		msg = proto.DHTMessage(key=key, hash=hash, type=type, **kwargs)
		self.node.send(dstId=hash, policy=proto.RoutedMessage.LEFT, dhtMsg=[msg]) #@UndefinedVariable
	def createHash(self, key, method="sha1"):
		digest = hashlib.new(method)
		digest.update(key)
		val = struct.unpack('Q', digest.digest()[-8:])[0]
		return val % config.MAX_ID
	def createRequest(self, **kwargs):
		return proto.DHTRequest(**kwargs)
