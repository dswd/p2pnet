import time, hashlib
from ... import config, proto

class Action:
	Protect = 0
	RetrieveValues = 1
	RetrieveMeta = 2
	RetrieveSubscribers = 3
	Publish = 4
	Delete = 5
	SetTimeout = 6
	Subscribe = 7

class Protection:
	class Method:
		Token = 1
		Priority = 2
		HashedSecretSHA1 = 3
	def __init__(self, actions, method, challenge, timeout):
		self.actions = actions
		self.method = method
		self.challenge = challenge
		self.timeout = timeout
		if not Action.Protect in actions:
			self.actions.append(Action.Protect)
		if not timeout:
			self.timeout = int(time.time()) + config.MAX_DHT_PROTECTION_TIMEOUT
	def _timedOut(self):
		return self.timeout <= int(time.time())
	def checkAction(self, action, credentials):
		if not action in self.actions:
			return True
		if self.method == self.Method.Token:
			return credentials == self.challenge
		elif self.method == self.Method.Priority:
			return credentials >= self.challenge
		elif self.method == self.Method.HashedSecretSHA1:
			return hashlib.sha1(credentials) == self.challenge
		else:
			return False
	def toProto(self):
		return proto.DHTEntry.Protection(
				method=self.method, challenge=self.challenge, timeoutTime=self.timeout,
				protectRetrieveValues=Action.RetrieveValues in self.actions,
    			protectRetrieveMeta=Action.RetrieveMeta in self.actions,
    	   		protectRetrieveSubscribers=Action.RetrieveSubscribers in self.actions,
    		    protectPublish=Action.Publish in self.actions,
    			protectDelete=Action.Delete in self.actions,
				protectSetTimeout=Action.SetTimeout in self.actions,
				protectSubscribe=Action.Subscribe in self.actions
		)
	@classmethod
	def fromProto(cls, p):
		actions = filter(bool, [
			p.protectRetrieveValues and Action.RetrieveValues,
			p.protectRetrieveMeta and Action.RetrieveMeta,
			p.protectRetrieveSubscribers and Action.RetrieveSubscribers,
			p.protectPublish and Action.Publish,
			p.protectDelete and Action.Delete,
			p.protectSetTimeout and Action.SetTimeout,
			p.protectSubscribe and Action.Subscribe
		])
		return Protection(method=p.method, challenge=p.challenge, timeout=p.timeoutTime, actions=actions)

class Subscription:
	def __init__(self, addr, timeout, actions):
		self.addr = addr
		self.timeout = timeout
		self.actions = actions
		if not timeout:
			self.timeout = int(time.time()) + config.MAX_DHT_SUBSCRIPTION_TIMEOUT
	def _timedOut(self):
		return self.timeout <= int(time.time())
	def toProto(self):
		return proto.DHTEntry.Subscription(
				addr=proto.ServiceAddress(id=self.addr[0], handle=self.addr[1]),
				timeoutTime=self.timeout,
				observeValues=Action.Publish in self.actions,
    			observeTimeout=Action.SetTimeout in self.actions,
				observeSubscribers=Action.Subscribe in self.actions,
				observeProtection=Action.Protect in self.actions
		)
	@classmethod
	def fromProto(cls, p):
		actions = filter(bool, [
			p.observeValues and Action.Publish,
			p.observeValues and Action.Delete,
			p.observeSubscribers and Action.Subscribe,
			p.observeTimeout and Action.SetTimeout,
			p.observeProtection and Action.Protect
		])
		return Subscription((p.addr.id, p.addr.handle), p.timeoutTime, actions)

class Entry:
	def __init__(self): #@ReservedAssignment
		self.values = []
		self.firstSeen = int(time.time())
		self.lastUpdate = int(time.time())
		self.timeout = int(time.time()) + config.MAX_DHT_TIMEOUT
		self.protection = None
		self.subscriptions = {}
	def _convertIndex(self, index):
		return (index-1) if index > 0 else (len(self.values) + index)
	def _convertRange(self, start, end):
		start = self._convertIndex(start) if start else 0
		end = (self._convertIndex(end)+1) if end else (len(self.values)+1)
		return slice(start, end)
	def _timedOut(self):
		return self.timeout <= int(time.time())
	def findSubscriptions(self, action):
		return filter(lambda s: action in s.actions, self.subscriptions.values())
	def getSubscription(self, addr):
		sub = self.subscriptions.get(addr)
		if sub and sub._timedOut():
			del self.subscriptions[addr]
		else:
			return sub
	def setSubscription(self, sub):
		self.subscriptions[sub.addr] = sub
		if sub._timedOut():
			del self.subscriptions[sub.addr]
	def isAllowed(self, action, credentials):
		if not self.protection:
			return True
		elif self.protection._timedOut():
			self.protection = None
			return True
		else:
			return self.protection.checkAction(action, credentials)
	def getValuesByIndex(self, indexes):
		values = []
		for index in indexes:
			values.append(self.values[self._convertIndex(index)])
		return values
	def getValuesByRange(self, start, end):
		return self.values[self._convertRange(start, end)]
	def addValues(self, position, values):
		if position < 0:
			position = len(self.values) + 2 + position
		self.values = self.values[:position] + values[:] + self.values[position:]
		self.lastUpdate = int(time.time())
	def delValuesByIndex(self, indexes):
		for index in sorted(map(self._convertIndex, indexes), reverse=True):
			del self.values[index]
		self.lastUpdate = int(time.time())
	def delValuesByRange(self, start, end):
		del self.values[self._convertRange(start, end)]
		self.lastUpdate = int(time.time())
	def valueCount(self):
		return len(self.values)
	def dataSize(self):
		return sum(map(len, self.values))
	def toProto(self, values, includeMeta, includeSubscribers):
		entry = proto.DHTEntry(value=values)
		if includeMeta:
			entry.firstSeen = self.firstSeen
			entry.timeout = self.timeout
			entry.lastUpdate = self.lastUpdate
			entry.valueCount = self.valueCount()
			entry.dataSize = self.dataSize()
			if self.protection and not self.protection._timedOut():
				entry.protection = self.protection.toProto()
		if includeSubscribers:
			entry.subscribers.extend(map(lambda s: s.toProto(), filter(lambda s: not s._timedOut(), self.subscriptions.values())))
		return entry

class Registry:
	def __init__(self):
		self.entries = {}
	def getEntry(self, hash, key): #@ReservedAssignment
		entr = self.entries.get((hash, key))
		if entr and entr._timedOut():
			del self.entries[(hash, key)]
		else:
			return entr
	def createEntry(self, hash, key): #@ReservedAssignment
		entr = Entry()
		self.entries[(hash, key)] = entr
		return entr
	def checkTimeout(self):
		timedOut = []
		for key, entry in self.entries.iteritems():
			if entry._timedOut():
				timedOut.append(key)
		for key in timedOut:
			del self.entries[key]