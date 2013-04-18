import logging, hashlib, struct, time

from ...base import Event
from ... import proto, config

import storage
from storage import Action

logger = logging.getLogger(__name__)

Event.TYPE_DHT_REPLY = "dht_reply"
Event.TYPE_DHT_EVENT = "dht_event"

class DHTException(Exception):
	def __init__(self, code, msg=None):
		self.code = code
		self.msg = msg

class Feature:
	NAME = "dht"
	def __init__(self, node):
		self.node = node
		node.addListener(self._handleRoutedMessage, Event.TYPE_MESSAGE_ROUTED)
		node.addListener(self._handlePeerListChanged, Event.TYPE_PEERLIST_CHANGED)
		node.features[Feature.NAME] = self
		self.entries = storage.Registry()
	def _checkAction(self, entry, action, credentials):
		if entry.isAllowed(action, credentials):
			return
		if credentials:
			raise DHTException(proto.DHTReply.AUTHENTICATION_INVALID) #@UndefinedVariable
		else:
			raise DHTException(proto.DHTReply.ENTRY_PROTECTED) #@UndefinedVariable
	def _handleRequest(self, dhtmsg, entry, request):
		if request.HasField("retrieve"):
			return (self._handleRequestRetrieve(dhtmsg, entry, request.retrieve), None)
		elif request.HasField("publish"):
			return (self._handleRequestPublish(dhtmsg, entry, request.publish), Action.Publish)
		elif request.HasField("delete"):
			return (self._handleRequestDelete(dhtmsg, entry, request.delete), Action.Delete)
		elif request.HasField("setTimeout"):
			return (self._handleRequestSetTimeout(dhtmsg, entry, request.setTimeout), Action.SetTimeout)
		elif request.HasField("subscribe"):
			return (self._handleRequestSubscribe(dhtmsg, entry, request.subscribe), Action.Subscribe)
		elif request.HasField("protect"):
			return (self._handleRequestProtect(dhtmsg, entry, request.protect), Action.Protect)
		else:
			raise DHTException(proto.DHTReply.REQUEST_INVALID) #@UndefinedVariable
	def _handleRequestRetrieve(self, dhtmsg, entry, retrieve):
		if retrieve.indexes and (retrieve.HasField("firstIndex") or retrieve.HasField("lastIndex")):
			raise DHTException(proto.ErrorCode.REQUEST_INVALID, "indexes must not be set when firstIndex or lastIndex is set") #@UndefinedVariable
		if retrieve.HasField("firstIndex") or retrieve.HasField("lastIndex"):
			self._checkAction(entry, Action.RetrieveValues, dhtmsg.credentials)
			values = entry.getValuesByRange(retrieve.firstIndex, retrieve.lastIndex)
		elif retrieve.indexes:
			self._checkAction(entry, Action.RetrieveValues, dhtmsg.credentials)
			values = entry.getValuesByIndex(retrieve.indexes)
		else:
			values = []
		if retrieve.includeMeta:
			self._checkAction(entry, Action.RetrieveMeta, dhtmsg.credentials)
		entr = entry.toProto(values=values, includeMeta=retrieve.includeMeta, includeSubscribers=retrieve.includeSubscribers)
		return proto.DHTReply(status=proto.DHTReply.SUCCESS, entry=entr) #@UndefinedVariable
	def _handleRequestPublish(self, dhtmsg, entry, publish):
		self._checkAction(entry, Action.Publish, dhtmsg.credentials)
		if not publish.values:
			return proto.DHTReply(status=proto.DHTReply.SUCCESS) #@UndefinedVariable
		if len(publish.values) + entry.valueCount() > config.MAX_DHT_VALUE_COUNT:
			raise DHTException(proto.ErrorCode.LIMIT_VALUE_COUNT) #@UndefinedVariable
		if max(map(len, publish.values)) > config.MAX_DHT_VALUE_SIZE:
			raise DHTException(proto.ErrorCode.LIMIT_VALUE_SIZE) #@UndefinedVariable
		if sum(map(len, publish.values)) + entry.dataSize() > config.MAX_DHT_ENTRY_SIZE:
			raise DHTException(proto.ErrorCode.LIMIT_ENTRY_SIZE) #@UndefinedVariable
		entry.addValues(publish.storeAt, publish.values)
		return proto.DHTReply(status=proto.DHTReply.SUCCESS) #@UndefinedVariable
	def _handleRequestDelete(self, dhtmsg, entry, delete):
		if delete.indexes and (delete.HasField("firstIndex") or delete.HasField("lastIndex")):
			raise DHTException(proto.ErrorCode.REQUEST_INVALID, "indexes must not be set when firstIndex or lastIndex is set") #@UndefinedVariable
		self._checkAction(entry, Action.Delete, dhtmsg.credentials)
		if delete.HasField("firstIndex") or delete.HasField("lastIndex"):
			entry.delValuesByRange(delete.firstIndex, delete.lastIndex)
		else:
			entry.delValuesByIndex(delete.indexes)
		return proto.DHTReply(status=proto.DHTReply.SUCCESS) #@UndefinedVariable
	def _handleRequestSetTimeout(self, dhtmsg, entry, setTimeout):
		self._checkAction(entry, Action.SetTimeout, dhtmsg.credentials)
		if setTimeout > config.MAX_DHT_TIMEOUT + int(time.time()):
			raise DHTException(proto.ErrorCode.LIMIT_TIMEOUT) #@UndefinedVariable
		entry.timeout = setTimeout
		return proto.DHTReply(status=proto.DHTReply.SUCCESS) #@UndefinedVariable
	def _handleRequestSubscribe(self, dhtmsg, entry, subscribe):
		self._checkAction(entry, Action.Subscribe, dhtmsg.credentials)
		if subscribe.timeoutTime > config.MAX_DHT_SUBSCRIPTION_TIMEOUT + int(time.time()):
			raise DHTException(proto.ErrorCode.LIMIT_TIMEOUT) #@UndefinedVariable
		entry.setSubscription(storage.Subscription.fromProto(subscribe))
		return proto.DHTReply(status=proto.DHTReply.SUCCESS) #@UndefinedVariable
	def _handleRequestProtect(self, dhtmsg, entry, protect):
		self._checkAction(entry, Action.Protect, dhtmsg.credentials)
		if protect.timeoutTime > config.MAX_DHT_PROTECTION_TIMEOUT + int(time.time()):
			raise DHTException(proto.ErrorCode.LIMIT_TIMEOUT) #@UndefinedVariable
		entry.protection = storage.Protection.fromProto(protect)
		return proto.DHTReply(status=proto.DHTReply.SUCCESS) #@UndefinedVariable
	def _handleDhtMessage(self, rmsg, dhtmsg):
		if dhtmsg.type == proto.DHTMessage.REPLY: #@UndefinedVariable
			self.node._event(type=Event.TYPE_DHT_REPLY, data=dhtmsg) #@UndefinedVariable
		elif dhtmsg.type == proto.DHTMessage.EVENT: #@UndefinedVariable
			self.node._event(type=Event.TYPE_DHT_EVENT, data=dhtmsg) #@UndefinedVariable
		elif dhtmsg.type == proto.DHTMessage.REQUEST: #@UndefinedVariable
			entry = self.entries.getEntry(dhtmsg.hash, dhtmsg.key)
			aborted = False
			replies = []
			events = {}
			for req in dhtmsg.request:
				if aborted:
					replies.append(proto.DHTReply(status=proto.DHTReply.SKIPPED)) #@UndefinedVariable
					continue
				try:
					if not entry:
						if req.HasField("retrieve") or req.HasField("delete"):
							raise DHTException(proto.DHTReply.ENTRY_UNKNOWN) #@UndefinedVariable
						else:
							entry = self.entries.createEntry(dhtmsg.hash, dhtmsg.key)
					reply, action = self._handleRequest(dhtmsg, entry, req) 
					replies.append(reply)
					for sub in entry.findSubscriptions(action):
						reqs, repls = events.get(sub.addr, ([], []))
						reqs.append(req)
						repls.append(reply)
						events[sub.addr] = (reqs, repls)
				except DHTException, err:
					if err.msg:
						replies.append(proto.DHTReply(status=proto.DHTReply.ERROR, errorCode=err.code, errorMsg=err.msg)) #@UndefinedVariable
					else:
						replies.append(proto.DHTReply(status=proto.DHTReply.ERROR, errorCode=err.code)) #@UndefinedVariable
					if dhtmsg.abortOnError:
						aborted = True
			self.node._reply(rmsg, dhtMsg=[proto.DHTMessage(type=proto.DHTMessage.REPLY, hash=dhtmsg.hash, key=dhtmsg.key, reply=replies)]) #@UndefinedVariable
			for addr, (reqs, repls) in events.iteritems():
				msg = proto.DHTMessage(key=dhtmsg.key, hash=dhtmsg.hash, type=proto.DHTMessage.EVENT, request=reqs, reply=repls) #@UndefinedVariable
				self.node.send(dstId=addr[0], dstHandle=addr[1], policy=proto.RoutedMessage.DROP, dhtMsg=[msg]) #@UndefinedVariable
	def _handleRoutedMessage(self, evt):
		msg = evt.getData()
		for dhtMsg in msg.dhtMsg:
			self._handleDhtMessage(msg, dhtMsg)
	def _handlePeerListChanged(self, evt):
		peers = evt.getData()
		#TODO: check if some data belongs to neighbors
	@classmethod
	def createHash(cls, key, method="sha1"):
		digest = hashlib.new(method)
		digest.update(key)
		val = struct.unpack('Q', digest.digest()[-8:])[0]
		return val % config.MAX_ID
	@classmethod
	def createRetrieveRequest(cls, **kwargs):
		return proto.DHTRequest(retrieve=proto.DHTRequest.Retrieve(**kwargs))
	@classmethod
	def createPublishRequest(cls, **kwargs):
		return proto.DHTRequest(publish=proto.DHTRequest.Publish(**kwargs))
	@classmethod
	def createDeleteRequest(cls, **kwargs):
		return proto.DHTRequest(delete=proto.DHTRequest.Delete(**kwargs))
	@classmethod
	def createProtectRequest(cls, **kwargs):
		return proto.DHTRequest(protect=proto.DHTEntry.Protection(**kwargs))
	@classmethod
	def createSetTimeoutRequest(cls, timeoutTime):
		return proto.DHTRequest(setTimeout=timeoutTime)
	@classmethod
	def createSubscribeRequest(cls, id, handle, **kwargs): #@ReservedAssignment
		return proto.DHTRequest(subscribe=proto.DHTEntry.Subscription(addr=proto.ServiceAddress(id=id, handle=handle), **kwargs))
	def sendRequests(self, key, requests, hash=None, **kwargs): #@ReservedAssignment
		if hash is None:
			hash = self.createHash(key) #@ReservedAssignment
		msg = proto.DHTMessage(key=key, hash=hash, type=proto.DHTMessage.REQUEST, request=requests, **kwargs) #@UndefinedVariable
		self.node.send(dstId=hash, policy=proto.RoutedMessage.LEFT, dhtMsg=[msg]) #@UndefinedVariable
