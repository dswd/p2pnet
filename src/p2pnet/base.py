import socket, random, logging, time
from google.protobuf import text_format #@UnresolvedImport

logger = logging.getLogger(__name__)

from . import net, proto, algorithm, config, event

# TODO: Part procedure
# TODO: Edge peers
# TODO: Public Keys
# TODO: Broadcast
# TODO: DHT
# TODO: Pub/Sub
# TODO: MessageQueues
# TODO: Traffic routing optimizations
# TODO: Forwardings

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

class Event(event.Event):
	"""
	undocumented
	"""
	TYPE_MESSAGE_ROUTED = "message_routed"
	TYPE_MESSAGE_JOIN = "message_join"
	TYPE_NODE_UNREACHABLE = "node_unreachable"
	TYPE_MESSAGE_INVALID = "message_invalid"
	def __init__(self, type, peer=None, node=None, data=None): #@ReservedAssignment
		event.Event.__init__(self, type, data)
		self.node = node
		self.peer = peer
	def getPeer(self):
		"""
		undocumented
		"""
		return self.peer
	def getNode(self):
		"""
		undocumented
		"""
		return self.node
	def __repr__(self):
		return "Event(%s, %s, %s, %r)" % (self.getType(), self.peer, self.node, self.getData())

class Peer:
	def __init__(self, node, connection):
		self.node = node
		self.con = connection
		self.init = None
		self.ident = None
		self.peers = []
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
	def _isAllowed(self):
		return self.getId() in self.node.peers
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
		if msg.HasField("join"):
			self._event(type=Event.TYPE_MESSAGE_JOIN, data=msg.join)
		if self._isAllowed():
			for rmsg in msg.routed:
				self.node._route(rmsg)
	def __str__(self):
		addr = "%s:%d" % self.getAddress()[1:]
		return "%d (%s)" % (self.ident.id, addr) if self.ident else addr
	def __repr__(self):
		return str(self)

class Node(event.Manager):
	def __init__(self):
		"""
		undocumented
		"""
		self.ident = proto.Peer(id=generateId(), reachable=True)
		event.Manager.__init__(self)
		logger.debug("Ident: %s", self.ident)
		logger.info("ID: %d", self.ident.id)
		self.net = net.Node(proto.BaseMessage)
		self.net.addListener(self._handleMessage, net.Event.TYPE_MESSAGE)
		self.net.addListener(self._handleConnect, net.Event.TYPE_CONNECT)
		self.net.addListener(self._handleDisconnect, net.Event.TYPE_DISCONNECT)
		self.peersByCon = {}
		self.peersById = {}
		self.peers = []
		self.edgePeers = []
		#FIXME: determine reachability
		self._rebuildIdent()
		self.net.schedule(self._sendPeerList, config.PEER_LIST_INTERVAL, repeated=True)
		self.net.schedule(self._cleanup, config.CLEANUP_INTERVAL, repeated=True)
	def _peerList(self, shouldReply):
		peers = [p.getIdent() for p in self._getPeers()]
		return  proto.PeerList(peers=peers, shouldReply=shouldReply)
	def _sendPeerListTo(self, peer, shouldReply):
		peer.send(peers=self._peerList(shouldReply))
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
	def getIdent(self):
		"""
		undocumented
		"""
		return self.ident
	def getId(self):
		"""
		undocumented
		"""
		return self.ident.id
	def _rebuildIdent(self):
		del self.ident.address[:] 
		self.ident.address.extend([encodeAddress(*addr) for addr in self.getAddresses()])
	def _getPeers(self):
		return self.peers + self.edgePeers
	def _getSuperPeers(self):
		return self.peers
	def _getEdgePeers(self):
		return self.edgePeers
	def _getImportantPeers(self):
		return self.peers
	def start(self):
		"""
		undocumented
		"""
		self.net.start()
	def stop(self):
		"""
		undocumented
		"""
		self.net.stop()
	def open(self, *args, **kwargs): #@ReservedAssignment
		"""
		undocumented
		"""
		addr = self.net.open(*args, **kwargs)
		self._rebuildIdent()
		return addr
	def close(self, *args, **kwargs):
		"""
		undocumented
		"""
		self.net.close(*args, **kwargs)
		self._rebuildIdent()
	def shutdown(self):
		"""
		undocumented
		"""
		self.net.shutdown()
	def getAddresses(self):
		"""
		undocumented
		"""
		return self.net.getAddresses()
	def _connectTo(self, ident):
		#TODO: try multiple addresses
		if not ident.address:
			return
		addr = decodeAddress(ident.address[0])
		con = self.net.getConnection(addr)
		if con:
			self._getPeer(con)
		con = self.net.connectTo(addr)
		return self._addConnection(con)
	def part(self):
		"""
		undocumented
		"""
		return
	def neighbors(self):
		return algorithm.neighbors(self._getPeers(), self.getId(), Peer.getId)
	def _handleConnect(self, event):
		self._addConnection(event.getConnection())
	def _getPeer(self, connection):
		return self.peersByCon.get(connection.getUuid())
	def _addConnection(self, connection):
		peer = self._getPeer(connection)
		if peer:
			return peer
		peer = Peer(self, connection)
		self.peersByCon[connection.getUuid()] = peer
		return peer
	def _removeConnection(self, connection):
		uuid = connection.getUuid()
		if uuid in self.peersByCon:
			peer = self.peersByCon[uuid]
			del self.peersByCon[uuid]
			return peer
	def _handleDisconnect(self, event):
		connection = event.getConnection()
		peer = self._removeConnection(connection)
		if not peer:
			logger.warn("Unknown connection disconnected: %s" % connection)
			return
		if peer.getIdent():
			if not peer.getId() in self.peersById:
				logger.warn("Unknown peer disconnected: %s" % peer)
				return
			if peer.con.getUuid() != self.peersById[peer.getId()].con.getUuid():
				#duplicate connection has been closed, no reaction
				return
			del self.peersById[peer.getId()]
		if peer in self._getImportantPeers():
			logger.warn("Lost peer: %s", peer)
			self.peers.remove(peer)
			try:
				self._connectTo(peer.getIdent())
			except Exception, exc: #@UnusedVariable
				logger.warn("Failed to reconnect to peer: %s", peer)
			self._updatePeers()
			self._sendPeerList() # Sending updated peer list to all peers
	def _handleMessage(self, event):
		connection = event.getConnection()
		message = event.getData()
		peer = self._getPeer(connection)
		if peer:
			peer._handleMessage(message)
		else:
			logger.warn("Ignoring message from unknown connection: %s", connection)
	def send(self, dstId, srcId=None, **kwargs):
		"""
		undocumented
		"""
		if isinstance(dstId, int):
			dstId = [dstId]
		if srcId is None:
			srcId = self.getId()
		rmsg = proto.RoutedMessage(srcId=srcId, dstId=dstId, **kwargs)
		self._route(rmsg)
	def _reply(self, msg, **kwargs):
		self.send(dstId=msg.srcId, srcHandle=msg.dstHandle, dstHandle=msg.srcHandle, **kwargs)
	def _routedError(self, dst, severity, code, **kwargs):
		self.send(dstId=dst, routedControl=[proto.Control(severity=severity, code=code, **kwargs)])
	def _route(self, rmsg):
		forMe, outList, dstUnknown = algorithm.route(rmsg, self.getId(), self._getPeers(), Peer.getId)
		for peer, msg in outList.iteritems():
			peer.send(routed=[msg])
		for msg in forMe:
			self._handleRoutedMessage(msg)
		if dstUnknown and not rmsg.routedControl:
			self._routedError(rmsg.srcId, proto.Control.ERROR, proto.Control.Routing_UnreachableId, id=dstUnknown) #@UndefinedVariable
	def _handleRoutedMessage(self, msg):
		# Message is for me
		for ctrl in msg.routedControl:
			if ctrl.code == proto.Control.Routing_UnreachableId: #@UndefinedVariable
				for id_ in ctrl.id:
					self._event(type=Event.TYPE_NODE_UNREACHABLE, node=id_, data=msg)
		self._event(type=Event.TYPE_MESSAGE_ROUTED, data=msg)
	def _event(self, **kwargs):
		event = Event(**kwargs)
		logger.info(event)
		self.triggerEvent(event)
	def _updatedIdent(self, peer):
		if peer.getId() in self.peersById:
			# Another connection exists with that peer, select one and close it.
			# Note: it is important that if both end detect this at the same time
			#       they select the same connection to be closed, thus using ordering.
			peer2 = self.peersById[peer.getId()]
			if peer.con.getUuid() < peer2.con.getUuid():
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
		# Only include allowed peers, i.e. existing peers and peers of peers
		for peer in self._getPeers():
			id_ = peer.getId()
			if not id_:
				continue
			knownNodes[id_] = peer
			for p in peer.peers:
				if not p.id in knownNodes:
					knownNodes[p.id] = p
		if self.getId() in knownNodes:
			del knownNodes[self.getId()]
		knownNodes = knownNodes.values()
		def idFn(n):
			return n.id if hasattr(n, "id") else n.getIdent().id
		left, right, long_ = algorithm.selectPeers(self, knownNodes, idFn=idFn)
		peers = {}
		for node in left+right+long_:
			id_ = idFn(node)
			if id_ in self.peersById.keys():
				peers[id_] = self.peersById[id_]
			else:
				try:
					self._connectTo(node)
				except:
					logger.warning("Failed to connect to %s in peer update", m2s(node))
		self.peers = peers.values()
