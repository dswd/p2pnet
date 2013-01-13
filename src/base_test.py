#!/usr/bin/python
# -*- coding: utf-8 -*-

if __name__ == "__main__":
	from p2pnet.test import run
	from p2pnet.base import Node
	from p2pnet.features import handles, ping
	node = Node()
	ping.Feature(node)
	handles.Feature(node)
	node.node = lambda :node
	def echo(*args): 
		print " ".join(map(str, args))
	node.echo = echo
	print "ID: %s" % node.getId()
	print "Address: %s" % (node.open()[1:],)
	node.start()
	run(node)