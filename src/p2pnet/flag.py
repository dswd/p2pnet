import os, select

class Flag:
	def __init__(self, state=False):
		self._readFd, self._writeFd = os.pipe()
		if state:
			self.set()
	def wait(self, timeout=None):
		ready, _, _ = select.select([self._readFd], [], [], timeout)
		return self._readFd in ready
	def isSet(self):
		return self.wait(0)
	def clear(self):
		if self.isSet():
			os.read(self._readFd, 1)
	def set(self): #@ReservedAssignment
		if not self.isSet():
			os.write(self._writeFd, "x")
	def fileno(self):
		return self._readFd
	def __del__(self):
		os.close(self._readFd)
		os.close(self._writeFd)