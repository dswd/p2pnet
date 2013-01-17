'''
Created on Jan 11, 2013

@author: schwerdel
'''

import logging

from ..base import Event, Peer
from .. import proto, algorithm

logger = logging.getLogger(__name__)

Event.TYPE_NETWORK_JOINED = "network_joined"

	
JOIN_STATE_PENDING = 1
JOIN_STATE_FINISHED = 2

class Feature:
	def __init__(self, node):
		self.node = node
		node.addListener(self._handleEvent, Event.TYPE_MESSAGE_JOIN)
		node.join = self.join
		self.joinState = {}
	def _handleEvent(self, evt):
		join = evt.getData()
		peer = evt.getPeer() 
		if join.step in [proto.Join.DISCOVER, proto.Join.ACCEPT]: #@UndefinedVariable
			self._handleJoinAsServer(peer, join)
		elif join.step in [proto.Join.FORWARD, proto.Join.OFFER, proto.Join.FINISHED]: #@UndefinedVariable
			self._handleJoinAsClient(peer, join)
	def join(self, *args, **kwargs):
		"""
		undocumented
		"""
		con = self.node.net.connect(*args, **kwargs)
		peer = self.node._addConnection(con)
		peer.send(join=proto.Join(step=proto.Join.DISCOVER)) #@UndefinedVariable
		self.joinState[peer] = proto.Join.DISCOVER #@UndefinedVariable
	def _handleJoinAsClient(self, peer, join):
		if not peer in self.joinState:
			# For security reasons we do not react on join messages that we did not trigger
			return
		if join.step == proto.Join.FORWARD: #@UndefinedVariable
			# Forgetting old peer and starting over with new peer
			del self.joinState[peer]
			peer = self.node._connectTo(join.nextPeer)
			peer.send(join=proto.Join(step=proto.Join.DISCOVER)) #@UndefinedVariable
			self.joinState[peer] = JOIN_STATE_PENDING
		elif join.step == proto.Join.OFFER: #@UndefinedVariable
			# Determine other neighbor from peer list
			neighbors = algorithm.neighbors(peer.peers[:] + [peer.ident], self.node.getId(), lambda p: p.id)
			otherPeer = filter(lambda p: p.id != peer.ident.id, neighbors)
			if otherPeer:
				# Start join process with that peer as well
				otherPeer = otherPeer[0]
				oPeer = self.node._connectTo(otherPeer)
				if not oPeer in self.joinState:
					self.joinState[oPeer] = JOIN_STATE_PENDING
					oPeer.send(join=proto.Join(step=proto.Join.DISCOVER)) #@UndefinedVariable
			# Send ACCEPT to the peer we got the OFFER from
			peer.send(join=proto.Join(step=proto.Join.ACCEPT)) #@UndefinedVariable
		elif join.step == proto.Join.FINISHED: #@UndefinedVariable
			# Fine, we are in the peer list of this peer
			self.joinState[peer] = JOIN_STATE_FINISHED
			for peer, jState in self.joinState.iteritems():
				if jState != JOIN_STATE_FINISHED:
					# Not all peers have added us to their peer lists
					return
			# Add all joined peers to our peer list and built initial peer list based on their peers
			for peer in self.joinState.keys():
				self.node.peers.append(peer)
			self.node._updatePeers()
			self.node._event(type=Event.TYPE_NETWORK_JOINED) #@UndefinedVariable
	def _handleJoinAsServer(self, peer, join):
		left, right = self.node.neighbors()
		if (not left and not right) or (left.getId() == right.getId()) or algorithm.isBetween(left.getId(), peer.getId(), right.getId()):
			if join.step == proto.Join.DISCOVER: #@UndefinedVariable
				peer.send(join=proto.Join(step=proto.Join.OFFER), peers=self.node._peerList(False)) #@UndefinedVariable
				#TODO: send DHT data
			elif join.step == proto.Join.ACCEPT: #@UndefinedVariable
				self.node.peers.append(peer)
				peer.send(join=proto.Join(step=proto.Join.FINISHED)) #@UndefinedVariable
		else:
			nextHop = algorithm.closestPeer(self.node._getPeers(), peer.getId(), Peer.getId)
			peer.send(join=proto.Join(step=proto.Join.FORWARD, nextPeer=nextHop.getIdent())) #@UndefinedVariable
