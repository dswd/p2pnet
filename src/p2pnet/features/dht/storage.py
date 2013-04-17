import time, hashlib
from ... import config

class Protection:
	class Action:
		Protect = 0
		RetrieveValues = 1
		RetrieveMeta = 2
		RetrieveSubscribers = 3
		Publish = 4
		Delete = 5
		SetTimeout = 6
		Subscribe = 7
	class Method:
		Token = 1
		Priority = 2
		HashedSecretSHA1 = 3
	def __init__(self, actions, method, challenge, timeout):
		self.actions = actions
		self.method = method
		self.challenge = challenge
		self.timeout = timeout
		if not self.Action.Protect in actions:
			self.actions.append(self.Action.Protect)
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

class Entry:
	def __init__(self): #@ReservedAssignment
		self.values = []
		self.firstSeen = int(time.time())
		self.lastUpdate = int(time.time())
		self.timeout = int(time.time()) + config.MAX_DHT_TIMEOUT
		self.protection = None
	def _convertIndex(self, index):
		return (index-1) if index > 0 else (len(self.values) + index)
	def _convertRange(self, start, end):
		start = self._convertIndex(start) if start else 0
		end = (self._convertIndex(end)+1) if end else (len(self.values)+1)
		return slice(start, end)
	def _timedOut(self):
		return self.timeout <= int(time.time())
	def checkProtection(self, action, credentials):
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