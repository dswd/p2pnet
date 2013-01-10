#!/usr/bin/python
# -*- coding: utf-8 -*-

if __name__ == "__main__":
	from test import run
	from base import Node
	node = Node()
	print "ID: %s" % node.getId()
	print "Address: %s" % (node.open()[1:],)
	node.start()
	run(node)