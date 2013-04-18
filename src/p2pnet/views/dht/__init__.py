
from ... import proto
from ...features import dht
from ...util import flag

class DHTView:
	def __init__(self, node):
		self.node = node
		self.dht = node.features[dht.Feature.NAME]
		self.node.addListener(self._onReply, [dht.Event.TYPE_DHT_REPLY]) #@UndefinedVariable
		self.node.addListener(self._onEvent, [dht.Event.TYPE_DHT_EVENT]) #@UndefinedVariable
		self.replyListeners = {}
	def _listenReply(self, key, hash, callback, onetime=True): #@ReservedAssignment
		self.replyListeners[(key, hash)] = (callback, onetime)
	def _unlistenReply(self, key, hash): #@ReservedAssignment
		del self.replyListeners[(key, hash)]
	def _onReply(self, ev):
		msg = ev.getData()
		callback, onetime = self.replyListeners.get((msg.key, msg.hash)) or (None, None)
		if callback:
			try:
				callback(msg)
			except:
				import traceback
				traceback.print_exc()
				pass
		if onetime:
			self._unlistenReply(msg.key, msg.hash)
	def _onEvent(self, ev):
		msg = ev.getData()
		#FIXME: do something with event
	def registry(self, hashMethod="sha1"):
		return Registry(self, hashFn=lambda key: self.dht.createHash(key, hashMethod))
	
class Registry:
	def __init__(self, view, hashFn):
		self.view = view
		self.hashFn = hashFn
	def entry(self, key, blocking=True):
		if blocking:
			return BlockingEntry(self.view, key, self.hashFn(key))
		else:
			return Entry(self.view, key, self.hashFn(key))
		
class Action:
	@classmethod
	def publish(cls, values=[], pos=-1):
		return dht.Feature.createPublishRequest(storeAt=pos, values=values)
	@classmethod
	def retrieve(cls, indexes=[], firstIndex=None, lastIndex=None, includeMeta=True, includeSubscribers=False):
		req = dht.Feature.createRetrieveRequest(indexes=indexes, includeMeta=includeMeta, includeSubscribers=includeSubscribers)
		if not firstIndex is None:
			req.retrieve.firstIndex = firstIndex
		if not lastIndex is None:
			req.retrieve.lastIndex = lastIndex
		return req
	@classmethod
	def delete(cls, indexes=[], firstIndex=None, lastIndex=None):
		req = dht.Feature.createDeleteRequest(indexes=indexes)
		if not firstIndex is None:
			req.delete.firstIndex = firstIndex
		if not lastIndex is None:
			req.delete.lastIndex = lastIndex
		return req
	@classmethod
	def setTimeout(cls, timeoutTime):
		return dht.Feature.createSetTimeoutRequest(timeoutTime)
	@classmethod
	def protect(cls, method, challenge, timeoutTime, protectRetrieveValues=False, protectRetrieveMeta=False,
			protectRetrieveSubscribers=True, protectPublish=True, protectDelete=True, 
			protectSetTimeout=True, protectSubscribe=False):
		return dht.Feature.createProtectRequest(method=method, challenge=challenge, timeoutTime=timeoutTime, 
			protectRetrieveValues=protectRetrieveValues, protectRetrieveMeta=protectRetrieveMeta,
			protectRetrieveSubscribers=protectRetrieveSubscribers, protectPublish=protectPublish,
			protectDelete=protectDelete, protectSetTimeout=protectSetTimeout, protectSubscribe=protectSubscribe)
	@classmethod
	def subscribe(cls, id, handle, timeoutTime, observeValues=True, observeSubscribers=False, #@ReservedAssignment
			observeTimeout=False, observeProtection=False):
		return dht.Feature.createSubscribeRequest(id=id, handle=handle, timeoutTime=timeoutTime,
			observeValues=observeValues, observeSubscribers=observeSubscribers,
			observeTimeout=observeTimeout, observeProtection=observeProtection)

	
class Entry:
	def __init__(self, view, key, hash): #@ReservedAssignment
		self.view = view
		self.key = key
		self.hash = hash
	def multicall(self, requests, callback=None):
		if callback:
			self.view._listenReply(self.key, self.hash, callback)
		self.view.dht.sendRequests(key=self.key, hash=self.hash, requests=requests)
	def singlecall(self, request, callback=None):
		self.multicall([request], callback)
	def publish(self, *args, **kwargs):
		return self.singlecall(Action.publish(*args, **kwargs))
	def retrieve(self, *args, **kwargs):
		return self.singlecall(Action.retrieve(*args, **kwargs))
	def delete(self, *args, **kwargs):
		return self.singlecall(Action.delete(*args, **kwargs))
	def protect(self, *args, **kwargs):
		return self.singlecall(Action.protect(*args, **kwargs))
	def setTimeout(self, *args, **kwargs):
		return self.singlecall(Action.setTimeout(*args, **kwargs))
	def subscribe(self, *args, **kwargs):
		return self.singlecall(Action.subscribe(*args, **kwargs))

class BlockingEntry(Entry):
	def __init__(self, view, key, hash, callTimeout=30.0): #@ReservedAssignment
		Entry.__init__(self, view, key, hash)
		self.callTimeout = callTimeout
	def multicall(self, requests):
		replies = []
		lock = flag.Flag()
		def callback(msg):
			replies.extend(msg.reply)
			lock.set()
		Entry.multicall(self, requests, callback)
		lock.wait(self.callTimeout)
		if not replies:
			raise Exception()
		return replies
	def singlecall(self, request):
		print proto.m2s(request)
		res = self.multicall([request])[0]
		if not res.status == proto.DHTReply.SUCCESS: #@UndefinedVariable
			raise Exception()
		return res
	def retrieve(self, *args, **kwargs):
		return Entry.retrieve(self, *args, **kwargs).entry
