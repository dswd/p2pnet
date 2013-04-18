import socket, thread, threading, select, cStringIO, logging, time, math

from google.protobuf.internal.decoder import _DecodeVarint as decodeVarint #@UnresolvedImport
from google.protobuf.internal.encoder import _EncodeVarint as createVarintEncoder #@UnresolvedImport
encodeVarint = createVarintEncoder

from . import config
from .util import timer, flag, event

logger = logging.getLogger(__name__)

def publicIp(family=socket.AF_INET):
	"""
	undocumented
	"""
	try:
		s = socket.socket(family, socket.SOCK_DGRAM)
		s.connect(('google.com', 0))
		ip = s.getsockname()[0]
		s.close()
		logger.info("Public IP address: %s", ip)
		return ip
	except socket.error, exc:
		logger.error("Failed to detect public IP address: %s", exc)
		return '127.0.0.1'

class Event(event.Event):
	"""
	undocumented
	"""
	TYPE_MESSAGE = "message"
	TYPE_DISCONNECT = "disconnect"
	TYPE_CONNECT = "connect"
	TYPE_MSG_TOO_LARGE = "msg_too_large"
	def __init__(self, type, address=None, connection=None, data=None): #@ReservedAssignment
		event.Event.__init__(self, type, data)
		self.address = address
		self.connection = connection
	def getAddress(self):
		"""
		undocumented
		"""
		return self.address
	def getConnection(self):
		"""
		undocumented
		"""
		return self.connection
	def __repr__(self):
		return "Event(%s, %s, %r)" % (self.getType(), self.address, self.getData())

class Connection:
	"""
	undocumented
	"""
	def __init__(self, node, socket, keepAlive=False):
		self.node = node
		self.baseMsg = node.msgType
		self.bufferSize = node.bufferSize
		self.msgSizeLimit = node.msgSizeLimit
		self.socket = socket
		self.address = (self.socket.family,) + self.socket.getpeername()
		self.uuid = sum(sorted([self.socket.getsockname(), self.socket.getpeername()]), (self.socket.family,))
		self.setupTime = time.time()
		self.lastMessageInTime = time.time()
		self.lastMessageOutTime = time.time()
		self.trafficIn = 0.0
		self.trafficOut = 0.0
		self.rbuffer = ""
		self.wmsgs = []
		self.rmsgs = []
		self.socket.setblocking(0)
		self.setKeepAlive(keepAlive)
		self.node.connections[self.address] = self
		self._event(type=Event.TYPE_CONNECT)
	def getSetupTime(self):
		"""
		undocumented
		"""
		return self.setupTime
	def getLastMessageInTime(self):
		"""
		undocumented
		"""
		return self.lastMessageInTime
	def getLastMessageOutTime(self):
		"""
		undocumented
		"""
		return self.lastMessageOutTime
	def getLastMessageTime(self):
		"""
		undocumented
		"""
		return max(self.lastMessageInTime, self.lastMessageOutTime)
	def getTrafficIn(self):
		"""
		undocumented
		"""
		return self.trafficIn * math.pow(0.5, (time.time() - self.lastMessageInTime)/config.TRAFFIC_AVERAGING)
	def getTrafficOut(self):
		"""
		undocumented
		"""
		return self.trafficOut * math.pow(0.5, (time.time() - self.lastMessageOutTime)/config.TRAFFIC_AVERAGING)
	def getTraffic(self):
		"""
		undocumented
		"""
		return self.getTrafficIn() + self.getTrafficOut()
	def getAddress(self):
		"""
		undocumented
		"""
		return self.address
	def setKeepAlive(self, flag):
		"""
		undocumented
		"""
		self.socket.setsockopt(socket.SOL_TCP, socket.SO_KEEPALIVE, flag)
	def getKeepAlive(self, address):
		"""
		undocumented
		"""
		return self.socket.getsockopt(socket.SOL_TCP, socket.SO_KEEPALIVE)
	def getUnsent(self):
		"""
		undocumented
		"""
		return self.wmsgs[:]
	def _writePending(self):
		return bool(self.wmsgs)
	def _receiveData(self):
		try:
			self.rbuffer += self.socket.recv(self.bufferSize)
		except Exception, exc: #@UnusedVariable
			#logger.exception(exc)
			return self.close()
		if not self.rbuffer:
			return self.close()
		while self.rbuffer:
			(size, pos) = decodeVarint(self.rbuffer, 0)
			if size > self.msgSizeLimit:
				self._event(type=Event.TYPE_MSG_TOO_LARGE)
				return self.close()
			if len(self.rbuffer) < size + pos:
				return
			data = self.rbuffer[pos:pos+size]
			self.rbuffer = self.rbuffer[pos+size:]
			msg = self.baseMsg()
			msg.ParseFromString(data)
			self.rmsgs.append(msg)
			self._updateStatsReceived(len(data))
	def _updateStatsReceived(self, length):
			now = time.time()
			diff = (now - self.lastMessageInTime)
			f = math.pow(0.5, diff/config.TRAFFIC_AVERAGING)
			self.trafficIn = self.trafficIn * f + (length/diff) * (1-f)
			self.lastMessageInTime = now
	def _updateStatsSent(self, length):
			now = time.time()
			diff = (now - self.lastMessageOutTime)
			f = math.pow(0.5, diff/config.TRAFFIC_AVERAGING)
			self.trafficOut = self.trafficOut * f + (length/diff) * (1-f)
			self.lastMessageOutTime = now
	def _receiveAll(self):
		msgs = self.rmsgs
		self.rmsgs = []
		return msgs
	def _triggerRead(self):
		self._receiveData()
		for msg in self._receiveAll():
			self._event(type=Event.TYPE_MESSAGE, data=msg)
	def _send(self, msg, force=False):
		size = msg.ByteSize()
		if size > self.msgSizeLimit:
			return self._event(type=Event.TYPE_MSG_TOO_LARGE, data=msg)
		buf = cStringIO.StringIO()
		encodeVarint(buf.write, size)
		buf.write(msg.SerializeToString())
		val = buf.getvalue()
		logger.debug("Message length: %d", len(val))
		self.socket.send(val, 0 if force else socket.MSG_DONTWAIT)
		self._updateStatsSent(len(val))
	def send(self, msg=None, force=False, **kwargs):
		"""
		undocumented
		"""
		if not msg:
			msg = self.baseMsg(**kwargs)
		assert isinstance(msg, self.baseMsg)
		try:
			self._send(msg, force)
			return True
		except Exception, exc: #@UnusedVariable
			#logger.exception(exc)
			self.wmsgs.append(msg)
			return False
	def _triggerWrite(self):
		try:
			while self.wmsgs:
				msg = self.wmsgs.pop(0)
				self._send(msg)
		except Exception, exc:
			logger.exception(exc)
			self.wmsgs.insert(0, msg)
	def fileno(self):
		return self.socket.fileno()
	def close(self):
		"""
		undocumented
		"""
		self.socket.close()
		if self.address in self.node.connections:
			del self.node.connections[self.address]
		self._event(type=Event.TYPE_DISCONNECT)
	def getUuid(self):
		"""
		undocumented
		"""
		return self.uuid
	def __str__(self):
		return str(self.uuid)
	def __repr__(self):
		return "Connection%s" % (self.uuid,)
	def _event(self, **kwargs):
		self.node._event(address=self.getAddress(), connection=self, **kwargs)

class Node(event.Manager):
	"""
	This class implements a networking node that communicates using protocol 
	buffer messages. 
	The messages are encoded using the protocol buffers	library and delimited
	by prepending a *varint-encoded* length value.
	The whole node implementation uses only one thread and waits for input on
	its connections using the select system call.  
	"""
	def __init__(self, msgType, msgSizeLimit=1<<20, bufferSize=4096):
		"""
		Creates a new protocol buffer node.
		
		Parameter *msgType*:
		  This is the class of the protocol buffers message type that is used
		  to communicate. Only messages of this type can be sent and received.
		  
		Parameter *msgSizeLimit*:
		  This parameter specifies the maximum message size in bytes. Sending
		  a message that is larger than this limit is an error. If a message is
		  received that is bigger than the limit, the connection is immediately
		  terminated.
		"""
		event.Manager.__init__(self)
		self.running = False
		self.msgType = msgType
		self.msgSizeLimit = msgSizeLimit
		self.bufferSize = bufferSize
		self.connections = {}
		self.servers = {}
		self._triggerFlag = flag.Flag()
	def start(self):
		"""
		Starts the node by starting its inner event loop in a thread.
		"""
		if self.isRunning():
			return
		thread.start_new_thread(self._run, ())
	def stop(self):
		"""
		Stops the node by stopping its inner event loop thread.
		"""
		self.running = False
	def isRunning(self):
		"""
		Checks whether the node is running.
		
		Return value:
		  *True* if the node is running, else *False*
		"""
		return self.running in threading.enumerate()
	def open(self, port=0, host='', addressFamily=socket.AF_INET): #@ReservedAssignment
		"""
		Opens a TCP server socket bound to the given address and port.
		
		Parameter *port*:
		  This parameter specifies the port that should be bound. The range of 
		  valid values and their meaning depends on the address family.
		  If the port number is *0*, a free port will be selected and bound. 
		  
		Parameter *host*:
		  This parameter specifies the host address that should be bound to. 
		  The range of valid values and their meaning depends on the address 
		  family.
		  If the host is *''*, all local addresses will be bound.
		
		Parameter *addressFamily*:
		  This parameter specifies the address family of the socket.
		
		Return value:
		  The actual address that the server socket has been bound to.
		  This value should be used to refer to the server socket in other 
		  calls.
		"""
		sock = socket.socket(addressFamily, socket.SOCK_STREAM)
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		sock.bind((host, port))
		sock.listen(5)
		addr = (sock.family,) + sock.getsockname()
		if not host:
			# avoid exposing things like 0.0.0.0 as host address
			addr = (sock.family,) + (publicIp(), sock.getsockname()[1])
		self.servers[addr] = sock
		return addr
	def close(self, address):
		"""
		Closes the given server socket.
		
		Parameter *address*:
		  The address of the server socket as returned by :func:`open()`.
		"""
		sock = self.servers[address]
		sock.close()
		del self.servers[address]
	def shutdown(self):
		"""
		Closes all server sockets, connections and stops the node.
		"""
		for addr in self.getAddresses():
			self.close(addr)
		for con in self.getConnections():
			con.close()
		self.stop()
	def getAddresses(self):
		"""
		Returns a list of all server socket addresses.
		
		Return value:
		  A list of all server socket addresses as returned by :func:`open()`.
		"""
		return self.servers.keys()
	def connectTo(self, addr):
		"""
		undocumented
		"""
		return self.connect(addr[1], addr[2], addr[0])
	def connect(self, host, port, addressFamily=socket.AF_INET):
		"""
		undocumented
		"""
		infos = socket.getaddrinfo(host, port, addressFamily)
		for info in infos:
			(fam, _, _, _, sockaddr) = info
			if fam == addressFamily:
				host, port = sockaddr
		address = (addressFamily, host, port)
		if address in self.connections.keys():
			return self.connections[address]
		sock = socket.socket(addressFamily, socket.SOCK_STREAM)
		sock.connect(address[1:])
		con = Connection(self, sock)
		self._triggerFlag.set() # Reset wait loop to include this connection
		return con
	def getConnection(self, address):
		"""
		undocumented
		"""
		infos = socket.getaddrinfo(address[1], address[2], address[0])
		for info in infos:
			(fam, _, _, _, sockaddr) = info
			if (fam,) + sockaddr in self.connections.keys():
				return self.connections[(fam,) + sockaddr]
		return None
	def getConnections(self):
		"""
		undocumented
		"""
		return self.connections.values()
	def _acceptConnection(self, sock):
		(socket, _) = sock.accept()
		Connection(self, socket)
	def _select(self):
		cons = filter(lambda c: c.fileno(), self.connections.values())
		servers = self.servers.values()
		rsocks = servers + cons + [self._triggerFlag]
		wsocks = filter(lambda c: c._writePending(), cons)
		timeout = max(min(timer.nextTimeout() or 10.0, 10.0), 0.0)
		self._triggerFlag.clear()
		(rlist, wlist, _) = select.select(rsocks, wsocks, rsocks, timeout)
		for sock in rlist:
			if sock in cons:
				sock._triggerRead()
			elif sock in servers:
				self._acceptConnection(sock)
		for sock in wlist:
			sock._triggerWrite()
		timer.check()		
	def _run(self):
		self.running = threading.currentThread()
		while self.running == threading.currentThread():
			try:
				self._select()
			except Exception, exc:
				if self.running:
					logger.exception(exc)
	def _event(self, **kwargs):
		event = Event(**kwargs)
		logger.info(event)
		self.triggerEvent(event)
	def schedule(self, func, timeout, repeated=False, strict=False, args=[], kwargs={}):
		timer.schedule(func, timeout, repeated, strict, args, kwargs)
		self._triggerFlag.set() # Reset wait loop to include this timer if it is close