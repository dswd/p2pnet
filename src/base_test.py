#!/usr/bin/python
# -*- coding: utf-8 -*-

if __name__ == "__main__":
	from p2pnet.test import run
	from p2pnet import createNode
	from p2pnet.base import Event
	node = createNode()
	def echo(*args): 
		print " ".join(map(str, args))
	def debug(self):
		for con in self.net.getConnections():
			print con, con.getTrafficIn(), con.getTrafficOut()
	node.debug = debug.__get__(node)
	node.echo = echo
	node.addListener(echo, Event.MATCH_ANY)
	print "ID: %s" % node.getId()
	print "Address: %s" % (node.open()[1:],)
	node.start()
	run(node)