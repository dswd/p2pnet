import copy, math, logging

from config import *

logger = logging.getLogger(__name__)

# Distance from id1 to id2 when going right
def diffRight(id1, id2):
	return (id2 - id1 + MAX_ID) % MAX_ID

# Distance from id1 to id2 when going left
def diffLeft(id1, id2):
	return (id1 - id2 + MAX_ID) % MAX_ID	
	
def diffBidi(id1, id2):
	return min(diffLeft(id1, id2), diffRight(id1, id2))

def relPos(my, other):
	p = diffRight(my, other)
	if p > MAX_ID/2:
		p = -diffLeft(my, other)
	return p
	
def relPosLog(my, other):
	rPos = relPos(my, other)
	if rPos:
		return math.log(abs(rPos))*rPos/abs(rPos)
	else:
		return 0

def setDst(msg, dstId=[], dstStart=None, dstEnd=None):
	msg.dstId[:] = dstId
	if dstStart or dstEnd:
		msg.dstStart = dstStart
		msg.dstEnd = dstEnd
	else:
		msg.ClearField("dstStart")
		msg.ClearField("dstEnd")
	return msg

def relPosSplit(me, nodes, idFn):
	_nodes = nodes[:]
	_nodes.append(me)
	meId = idFn(me)
	_nodes.sort(key=lambda n: relPos(meId, idFn(n)))
	index = _nodes.index(me)
	return (_nodes[:index], _nodes[index+1:])

def closestPeer(peers, dstId, idFn, diff=diffBidi):
	minDiff = MAX_ID
	minPeer = None
	for peer in peers:
		peerId = idFn(peer) 
		if diff(peerId, dstId) < minDiff:
			minDiff = diff(peerId, dstId)
			minPeer = peer
	return minPeer
	
	
def route(msg, ident, peers):
	assert isinstance(msg, proto.RoutedMessage)
	logger.debug("Forwarding:\n%s", msg)
	outDst = {} # outgoing unicast messages per next hop as a list
	forMe = [] # messages that are for me
	dstUnknown = [] # unknown destination IDs
	
	# TTL handling
	# decrement TTL if present, set to default otherwise
	if msg.HasField("ttl"):
		msg.ttl -= 1
	else:
		msg.ttl = DEFAULT_TTL
	# limit TTL to MAX_TTL
	if msg.ttl > MAX_TTL:
		msg.ttl = MAX_TTL

	# Unicast destinations
	for dstId in msg.dstId:
		# check if message is for us
		if dstId == ident.id:
			forMe.append(setDst(copy.deepcopy(msg), [dstId]))
			continue

		# check if we are the closest peer to the left of dstId
		if msg.policy == proto.RoutedMessage.LEFT:
			closestLeft = closestPeer(peers, dstId, diff=diffRight)
			if diffRight(ident.id, dstId) <= diffRight(closestLeft.ident.id, dstId):
				forMe.append(setDst(copy.deepcopy(msg), [dstId]))
				continue					
					
		# check if we are the closest peer to the right of dstId
		if msg.policy == proto.RoutedMessage.RIGHT:
			closestRight = closestPeer(peers, dstId, diff=diffLeft)
			if diffLeft(ident.id, dstId) <= diffLeft(closestRight.ident.id, dstId):
				forMe.append(setDst(copy.deepcopy(msg), [dstId]))
				continue					
					
		# find closest peer in peer list
		nextHop = closestPeer(peers, dstId, diff=diffBidi)
		logger.debug("Next hop for %d: %s", dstId, nextHop)

		if diffBidi(ident.id, dstId) <= diffBidi(nextHop.ident.id, dstId):
			# next hop must be closer
			nextHop = None
			
		if not nextHop:
			logger.warning("Unable to find next hop for %d", dstId)
			if msg.policy == proto.RoutedMessage.NOTIFY:
				dstUnknown.append(dstId)
				continue
			elif msg.policy == proto.RoutedMessage.CLOSEST:
				forMe.append(setDst(copy.deepcopy(msg, [dstId])))
				continue
			elif msg.policy == proto.RoutedMessage.DROP:
				continue
			elif msg.policy == proto.RoutedMessage.LEFT:
				nextHop = closestPeer(peers, dstId, diff=diffRight)
			elif msg.policy == proto.RoutedMessage.RIGHT:
				nextHop = closestPeer(peers, dstId, diff=diffLeft)
		if nextHop:
			outDst[nextHop] = outDst.get(nextHop, [])
			outDst[nextHop].append(dstId)

	# merge outgoing messages with same next hop
	outList = {}
	for hop, dst in outDst.iteritems():
		outList[hop]=setDst(copy.deepcopy(msg), dst)
	
	if msg.ttl == 0:
		#FIXME: send control message
		logger.warning("Message reached zero ttl:\n%s", msg)
		outList = []
		dstUnknown = []
	
	# Broadcast message
	if msg.HasField("dstStart") and msg.HasField("dstEnd"):
		left, right = relPosSplit(ident, list(peers))
		#FIXME: broadcast
		logger.warning("Broadcast not supported yet, dropping message")
		
	return (forMe, outList, dstUnknown)


def selectPeers(me, nodes, idFn):
	if not nodes:
		return ([],[],[])
	#sort nodes to the left and right of our node
	left, right = relPosSplit(me, nodes, idFn)
	#retrieve S/2 left and S/2 right short peers
	short_nodes = right + left
	short_right = short_nodes[:MAX_SHORT/2]
	short_nodes.reverse()
	short_left = short_nodes[:MAX_SHORT/2]
	#calculate covered logarithmic ID space for all nodes
	long_nodes_pos = [(None, -math.log(MAX_ID/2))] + [(n, relPosLog(idFn(me), idFn(n))) for n in left] + [(None, 0)] +	[(n, relPosLog(idFn(me), idFn(n))) for n in right] + [(None, math.log(MAX_ID/2))]
	long_nodes_space = []
	for i in xrange(1, len(long_nodes_pos)-1):
		if long_nodes_pos[i][0]:
			long_nodes_space.append((long_nodes_pos[i][0], long_nodes_pos[i+1][1] - long_nodes_pos[i-1][1]))
	long_nodes_space.sort(key=lambda n: -n[1])
	#select L long peers with largest log space to minimize sum of squares 
	long_peers = [n[0] for n in long_nodes_space[:MAX_LONG]]
	#print "----------------------------------"
	#print "Self: %d" % ident.id
	#print "Known nodes: %s" % [n.ident.id for n in nodes]
	#print "----------------------------------"
	#print "Short left: %s" % [n.ident.id for n in short_left]
	#print "Short right: %s" % [n.ident.id for n in short_right]
	#print "Long peers: %s" % [n.ident.id for n in long_peers]
	#print "----------------------------------"
	return (short_left, short_right, long_peers)
