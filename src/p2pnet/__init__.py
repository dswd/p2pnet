from . import base, features

def createNode():
	node = base.Node()
	features.ping.Feature(node)
	features.handles.Feature(node)
	features.join.Feature(node)
	features.dht.Feature(node)
	return node