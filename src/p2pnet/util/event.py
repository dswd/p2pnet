import logging

logger = logging.getLogger(__name__)

class Event:
	"""
	undocumented
	"""
	MATCH_ANY = "*"
	def __init__(self, type, data=None): #@ReservedAssignment
		self.type = type
		self.data = data
	def getType(self):
		"""
		undocumented
		"""
		return self.type
	def getData(self):
		"""
		undocumented
		"""
		return self.data
	def __repr__(self):
		return "Event(%s, %r)" % (self.type, self.data)

class Manager:
	"""
	undocumented
	"""
	def __init__(self):
		self._listeners = {}
	def addListener(self, listener, event=Event.MATCH_ANY):
		"""
		undocumented
		"""
		if isinstance(event, list):
			for ev in event:
				self.addListener(listener, ev)
		else:
			if not event in self._listeners:
				self._listeners[event] = set()
			self._listeners[event].add(listener)
	def removeListener(self, listener, event=Event.MATCH_ANY):
		"""
		undocumented
		"""
		if isinstance(event, list):
			for ev in event:
				self.removeListener(listener, ev)
		else:
			if not event in self._listeners:
				self._listeners[event] = set()
			self._listeners[event].remove(listener)
	def triggerEvent(self, event):
		for ev in [event.getType(), Event.MATCH_ANY]:
			for listener in self._listeners.get(ev, []):
				try:
					listener(event)
				except Exception, exc:
					logger.exception(exc)