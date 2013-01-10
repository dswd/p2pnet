import net, proto, algorithm, timer, config, time
import socket, random, logging
from google.protobuf import text_format

logger = logging.getLogger(__name__)

def generateId():
	return random.randint(0, config.MAX_ID)

def encodeAddress(family, host, port):
	familyEnc = {socket.AF_INET: proto.Address.IPv4_TCP, socket.AF_INET6: proto.Address.IPv6_TCP}.get(family) #@UndefinedVariable
	hostEnc = socket.inet_pton(family, host)
	return proto.Address(type=familyEnc, address=hostEnc, port=port)

def decodeAddress(addr):
	familyDec = {proto.Address.IPv4_TCP: socket.AF_INET, proto.Address.IPv6_TCP:socket.AF_INET6}.get(addr.type) #@UndefinedVariable 
	hostDec = socket.inet_ntop(familyDec, addr.address)
	return (familyDec, hostDec, addr.port)

def m2s(msg):
	return text_format.MessageToString(msg, as_one_line=True)

class Event:
	"""
	undocumented
	"""
	TYPE_MESSAGE_DIRECT = "message_direct"
	TYPE_MESSAGE_ROUTED = "message_routed"
	TYPE_MESSAGE_INVALID = "message_invalid"
	TYPE_DISCONNECT = "disconnect"
	TYPE_CONNECT = "connect"
	def __init__(self, type, peer=None, data=None): #@ReservedAssignment
		self.type = type
		self.peer = peer
		self.data = data
	def getType(self):
		"""
		undocumented
		"""
		return self.type
	def getPeer(self):
		"""
		undocumented
		"""
		return self.peer
	def getData(self):
		"""
		undocumented
		"""
		return self.data
	def __repr__(self):
		return "Event(%s, %s, %r)" % (self.type, self.peer, self.data)

class Peer:
	def __init__(self, node, connection):
		self.node = node
		self.con = connection
		self.init = None
		self.ident = None
		self.peers = []
		self.node.peersByCon[connection.getUuid()] = self
		self.con.send(init=config.INITIALIZATION_MESSAGE, ident=self.node.getIdent())
	def getAddress(self):
		return self.con.getAddress()
	def getIdent(self):
		return self.ident
	def getId(self):
		return self.ident.id
	def send(self, msg=None, force=False, **kwargs):
		if not msg:
			msg = self.con.baseMsg(**kwargs)
		self.con.send(msg, force)
		logger.debug("Message to %s:\n%s", self, m2s(msg))
	def disconnect(self):
		self.con.close()
	def _event(self, **kwargs):
		self.node._event(peer=self, **kwargs)
	def _handleMessage(self, msg):
		if not self.init and msg.init:
			self.init = msg.init
		if not self.init:
			self._event(type=Event.TYPE_MESSAGE_INVALID, data=msg)
			logger.warn("Ignoring message before init")
			return
		if not self.ident and msg.ident:
			self.ident = msg.ident
			self.node._updatedIdent(self)
		if not self.ident:
			self._event(type=Event.TYPE_MESSAGE_INVALID, data=msg)
			logger.warn("Ignoring message before ident")
			return
		if msg.peers:
			self.peers = msg.peers.peers
			#FIXME: only if complete
			self.node._updatePeers()
			if msg.peers.shouldReply:
				self.node._sendPeerListTo(self, shouldReply=False)
		for rmsg in msg.routed:
			self.node.route(rmsg)
	def __str__(self):
		addr = "%s:%d" % self.getAddress()[1:]
		return "%d (%s)" % (self.ident.id, addr) if self.ident else addr
	def __repr__(self):
		return str(self)

class Node:
	def __init__(self):
		self.ident = proto.Peer(id=generateId(), reachable=True)
		self.listeners = []
		logger.debug("Ident: %s", self.ident)
		logger.info("ID: %d", self.ident.id)
		self.net = net.Node(proto.BaseMessage)
		self.net.addListener(self._handleEvent)
		self.peersByCon = {}
		self.peersById = {}
		self.peers = []
		self.otherPeers = []
		self.edgePeers = []
		#FIXME: determine reachability
		self._rebuildIdent()
		timer.schedule(self._sendPeerList, config.PEER_LIST_INTERVAL, repeated=True)
		timer.schedule(self._cleanup, config.CLEANUP_INTERVAL, repeated=True)
	def _sendPeerListTo(self, peer, shouldReply):
		peers = [peer.getIdent() for peer in self._getPeers()]
		peer.send(peers=proto.PeerList(peers=peers, shouldReply=shouldReply))
	def _sendPeerList(self):
		for p in self._getPeers():
			self._sendPeerListTo(p, shouldReply=True)
	def _cleanup(self):
		for con in self.net.getConnections():
			# Remove connection if no messages have been sent recently
			# Note: Important peers exchange peer lists and thus keep the 
			#       connection alive on both ends. 
			if time.time() - con.getLastMessageTime() > config.CONNECTION_TIMEOUT:
				con.close()
				continue
	def node(self):
		return self
	def getIdent(self):
		return self.ident
	def getId(self):
		return self.ident.id
	def _rebuildIdent(self):
		del self.ident.address[:] 
		self.ident.address.extend([encodeAddress(*addr) for addr in self.getAddresses()])
	def _getPeers(self):
		return self.peers + self.edgePeers + self.otherPeers
	def _getSuperPeers(self):
		return self.peers + self.otherPeers
	def _getEdgePeers(self):
		return self.edgePeers
	def _getImportantPeers(self):
		return self.peers
	def start(self):
		self.net.start()
	def stop(self):
		self.net.stop()
	def open(self, *args, **kwargs):
		addr = self.net.open(*args, **kwargs)
		self._rebuildIdent()
		return addr
	def close(self, *args, **kwargs):
		self.net.close(*args, **kwargs)
		self._rebuildIdent()
	def shutdown(self):
		self.net.shutdown()
	def getAddresses(self):
		return self.net.getAddresses()
	def join(self, *args, **kwargs):
		self.net.connect(*args, **kwargs)
	def _connectTo(self, ident):
		#TODO: try multiple addresses
		if not ident.address:
			return
		addr = decodeAddress(ident.address[0])
		if self.net.getConnection(addr):
			return
		print "Connect: %s" % (addr,)
		self.net.connectTo(addr)
	def part(self):
		return
	def _handleConnect(self, address, connection):
		peer = Peer(self, connection)
		self._sendPeerListTo(peer, shouldReply=True) #TODO: remove
	def _getPeer(self, connection):
		return self.peersByCon.get(connection.getUuid())
	def _removeConnection(self, connection):
		uuid = connection.getUuid()
		if uuid in self.peersByCon:
			peer = self.peersByCon[uuid]
			del self.peersByCon[uuid]
			return peer
	def _handleDisconnect(self, address, connection):
		peer = self._removeConnection(connection)
		if not peer:
			logger.warn("Unknown connection disconnected: %s" % connection)
			return
		if peer.getIdent():
			if not peer.getId() in self.peersById:
				logger.warn("Unknown peer disconnected: %s" % peer)
				return
			if peer != self.peersById[peer.getId()]:
				#duplicate connection has been closed, no reaction
				return
			del self.peersById[peer.getId()]
		if peer in self._getImportantPeers():
			logger.warn("Lost peer: %s" % peer)
			try:
				self._connectTo(peer.getIdent())
			except Exception, exc:
				logger.exception(exc)
				logger.warn("Failed to reconnect to peer: %s" % peer)
			self._updatePeers()
	def _handleMessage(self, address, connection, message):
		peer = self._getPeer(connection)
		if peer:
			peer._handleMessage(message)
		else:
			logger.warn("Ignoring message from unknown connection: %s" % connection)
	def _handleEvent(self, event):
		if event.type == net.Event.TYPE_MESSAGE:
			self._handleMessage(event.getAddress(), event.getConnection(), event.getData())
		elif event.type == net.Event.TYPE_CONNECT:
			self._handleConnect(event.getAddress(), event.getConnection())
		elif event.type == net.Event.TYPE_DISCONNECT:
			self._handleDisconnect(event.getAddress(), event.getConnection())
	def route(self, rmsg):
		#TODO: implement
		pass
	def addListener(self, listener):
		"""
		undocumented
		"""
		self.listeners.add(listener)
	def removeListener(self, listener):
		"""
		undocumented
		"""
		self.listeners.remove(listener)
	def _event(self, **kwargs):
		event = Event(**kwargs)
		logger.info(event)
		for listener in self.listeners:
			try:
				listener(event)
			except Exception, exc:
				logger.exception(exc)
	def _updatedIdent(self, peer):
		if peer.getId() in self.peersById:
			# Another connection exists with that peer, select one and close it.
			# Note: it is important that if both end detect this at the same time
			#       they select the same connection to be closed, thus using ordering.
			peer2 = self.peersById[peer.getId()]
			if peer.con.getUuid() > peer2.con.getUuid():
				self.peersById[peer.getId()] = peer
			return
		if peer.getId() == self.getId():
			if peer.getIdent() == self.getIdent():
				logger.warn("Connected to self, closing connection")
				peer.disconnect()
			return
		self.peersById[peer.getId()] = peer
		self._updatePeers()
	def _updatePeers(self):
		knownNodes = {}
		for id, peer in self.peersById.iteritems():
			knownNodes[id] = peer
			for p in peer.peers:
				knownNodes[p.id] = p
		if self.getId() in knownNodes:
			del knownNodes[self.getId()]
		knownNodes = knownNodes.values()
		def idFn(n):
			return n.id if hasattr(n, "id") else n.getIdent().id
		left, right, long = algorithm.selectPeers(self, knownNodes, idFn=idFn)
		peers = {}
		for node in left+right+long:
			id = idFn(node)
			if id in self.peersById.keys():
				peers[id] = self.peersById[id]
			else:
				self._connectTo(node)
		self.peers = peers.values()
