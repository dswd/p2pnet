#!/usr/bin/python
# -*- coding: utf-8 -*-

if __name__ == "__main__":
	from p2pnet.test import run
	from p2pnet.net import Node
	from p2pnet.proto import BaseMessage
	node = Node(BaseMessage)
	node.start()
	run(node)