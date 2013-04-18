#!/usr/bin/python
# -*- coding: utf-8 -*-

if __name__ == "__main__":
	from p2pnet.util.test import run
	from p2pnet.net import Node, Event
	from p2pnet.proto import BaseMessage
	node = Node(BaseMessage)
	def echo(*args): 
		print " ".join(map(str, args))
	node.echo = echo
	node.addListener(echo, Event.MATCH_ANY)
	node.start()
	run(node)