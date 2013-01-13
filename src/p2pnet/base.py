import net, proto, algorithm, timer, config, time
import socket, random, logging
from google.protobuf import text_format #@UnresolvedImport

logger = logging.getLogger(__name__)

# TODO: Join/Part procedure
# TODO: Edge peers
# TODO: Public Keys
# TODO: Broadcast
# TODO: DHT
# TODO: Pub/Sub
# TODO: MessageQueues
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

class Event:
	"""
	undocumented
	"""
	TYPE_MESSAGE_ROUTED = "message_routed"
	TYPE_NODE_UNREACHABLE = "node_unreachable"
	TYPE_MESSAGE_INVALID = "message_invalid"
	def __init__(self, type, node=None, data=None): #@ReservedAssignment
		self.type = type
		self.node = node
		self.data = data
	def getType(self):
		"""
		undocumented
		"""
		return self.type
	def getNode(self):
		"""
		undocumented
		"""
		return self.node
	def getData(self):
		"""
		undocumented
		"""
		return self.data
	def __repr__(self):
		return "Event(%s, %s, %r)" % (self.type, self.node, self.data)

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
			self.node._handleJoin(self, msg.join)
		if self._isAllowed():
			for rmsg in msg.routed:
				self.node._route(rmsg)
	def __str__(self):
		addr = "%s:%d" % self.getAddress()[1:]
		return "%d (%s)" % (self.ident.id, addr) if self.ident else addr
	def __repr__(self):
		return str(self)

class Node:
	def __init__(self):
		"""
		undocumented
		"""
		self.ident = proto.Peer(id=generateId(), reachable=True)
		self.listeners = []
		logger.debug("Ident: %s", self.ident)
		logger.info("ID: %d", self.ident.id)
		self.net = net.Node(proto.BaseMessage)
		self.net.addListener(self._handleEvent)
		self.peersByCon = {}
		self.peersById = {}
		self.peers = []
		self.edgePeers = []
		self.joinState = {}
		#FIXME: determine reachability
		self._rebuildIdent()
		timer.schedule(self._sendPeerList, config.PEER_LIST_INTERVAL, repeated=True)
		timer.schedule(self._cleanup, config.CLEANUP_INTERVAL, repeated=True)
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
	def join(self, *args, **kwargs):
		"""
		undocumented
		"""
		self.net.connect(*args, **kwargs)
	def _connectTo(self, ident):
		#TODO: try multiple addresses
		if not ident.address:
			return
		addr = decodeAddress(ident.address[0])
		if self.net.getConnection(addr):
			return
		self.net.connectTo(addr)
	def part(self):
		"""
		undocumented
		"""
		return
	def neighbors(self):
		return algorithm.neighbors(self._getPeers(), self.getId(), Peer.getId)
	def _handleJoin(self, peer, join):
		if join.step in [proto.Join.DISCOVER, proto.Join.ACCEPT]: #@UndefinedVariable
			self._handleJoinAsServer(peer, join)
		elif join.step in [proto.Join.FORWARD, proto.Join.OFFER, proto.Join.FINISHED]: #@UndefinedVariable
			self._handleJoinAsClient(peer, join)
	def _handleJoinAsClient(self, peer, join):
		if not peer in self.joinState:
			return
		if join.step == proto.Join.FORWARD: #@UndefinedVariable
			del self.joinState[peer]
			self._connectTo(join.nextPeer)
		elif join.step == proto.Join.OFFER: #@UndefinedVariable
			self.joinState[peer] = proto.Join.ACCEPT #@UndefinedVariable
			peer.send(join=proto.Join(step=proto.Join.ACCEPT)) #@UndefinedVariable
			#TODO: determine second peer and its join state
			# send discover to second peer it no join state
		elif join.step == proto.Join.FINISHED: #@UndefinedVariable
			#TODO: determine other peer join state
			# if both peers have join state finished
			#   add both peers as peers and emit joined event
			self.peers.append(peer)
			self._updatePeers()
	def _handleJoinAsServer(self, peer, join):
		left, right = self.neighbors()
		if (not left and not right) or (left.getId() == right.getId()) or algorithm.isBetween(left.getId(), peer.getId(), right.getId()):
			if join.step == proto.Join.DISCOVER: #@UndefinedVariable
				peer.send(join=proto.Join(step=proto.Join.OFFER), peers=self._peerList(False)) #@UndefinedVariable
				#TODO: send DHT data
			elif join.step == proto.Join.ACCEPT: #@UndefinedVariable
				self.peers.append(peer)
				peer.send(join=proto.Join(step=proto.Join.FINISHED)) #@UndefinedVariable
		else:
			nextHop = algorithm.closestPeer(self._getPeers(), peer.getId(), Peer.getId)
			peer.send(join=proto.Join(step=proto.Join.FORWARD, nextPeer=nextHop.getIdent())) #@UndefinedVariable
	def _handleConnect(self, address, connection):
		peer = Peer(self, connection)
		if not self.peers:
			peer.send(join=proto.Join(step=proto.Join.DISCOVER)) #@UndefinedVariable
			self.joinState[peer] = proto.Join.DISCOVER #@UndefinedVariable
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
			if peer.con.getUuid() != self.peersById[peer.getId()].con.getUuid():
				#duplicate connection has been closed, no reaction
				return
			del self.peersById[peer.getId()]
		if peer in self._getImportantPeers():
			logger.warn("Lost peer: %s" % peer)
			self.peers.remove(peer)
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
	def addListener(self, listener):
		"""
		undocumented
		"""
		self.listeners.append(listener)
	def removeListener(self, listener):
		"""
		undocumented
		"""
		self.listeners.remove(listener)
	def _event(self, **kwargs):
		event = Event(**kwargs)
		logger.info(event)
		print event
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
				self._connectTo(node)
		self.peers = peers.values()
