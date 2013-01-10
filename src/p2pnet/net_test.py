#!/usr/bin/python
# -*- coding: utf-8 -*-

if __name__ == "__main__":
	from test import run
	from net import Node
	from proto import BaseMessage
	node = Node(BaseMessage)
	node.start()
	run(node)