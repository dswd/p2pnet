#!/usr/bin/python
# -*- coding: utf-8 -*-

from p2pnet.base import Event
from p2pnet.proto import m2s
import logging

class Control:
	def __init__(self, node):
		self.node = node
		self.net = node.net
		self.dht = node.features.get("p2pnet.features.dht")
		self.node.addListener(self.onDhtReply, ["dht_reply"])
		self.watchEvents()
		self.DEBUG = logging.DEBUG
		self.INFO = logging.INFO
		self.WARNING = logging.WARNING
		self.ERROR = logging.ERROR
		self.FATAL = logging.FATAL
		self.setLogLevel(self.WARNING, 'p2pnet.net')
		self.setLogLevel(self.INFO, 'p2pnet.base')
	def onDhtReply(self, event):
		print m2s(event.data)
	def watchEvents(self, events=Event.MATCH_ANY):
		self.node.addListener(self.echo, events)
	def unwatchEvents(self, events=Event.MATCH_ANY):
		self.node.removeListener(self.echo, events)
	def setLogLevel(self, level, logger=None):
		logging.getLogger(logger).setLevel(level)
	def echo(self, *args): 
		print " ".join(map(str, args))
	def debug(self):
		for con in self.net.getConnections():
			print con, con.getTrafficIn(), con.getTrafficOut()
	def join(self, *args, **kwargs):
		return self.node.join(*args, **kwargs)

if __name__ == "__main__":
	from p2pnet.test import run
	from p2pnet import createNode
	node = createNode()
	print "ID: %s" % node.getId()
	print "Address: %s" % (node.open()[1:],)
	node.start()
	run(Control(node))