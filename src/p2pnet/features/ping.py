'''
Created on Jan 11, 2013

@author: schwerdel
'''

import time, random, logging

from ..base import Event
from .. import proto, timer

logger = logging.getLogger(__name__)

Event.TYPE_HANDLE_UNBOUND = "handle_unbound"

class Feature:
    def __init__(self, node):
        self.node = node
        node.addListener(self._handleEvent, Event.TYPE_MESSAGE_ROUTED)
        node.ping = self.ping
        self.pings = {}
    def _handleEvent(self, evt):
        msg = evt.getData()
        if not msg.HasField("pingMsg"):
            return
        ping = msg.pingMsg
        print ping
        if ping.type == proto.PingMessage.PING: #@UndefinedVariable
            self.node._reply(msg, pingMsg=proto.PingMessage(type=proto.PingMessage.PONG, id=ping.id, data=ping.data)) #@UndefinedVariable
        elif ping.type == proto.PingMessage.PONG: #@UndefinedVariable
            recv = time.time()
            if not ping.id in self.pings:
                print ping.id
                print self.pings
                logger.warn("Received unrequested ping reply")
                return
            sent, callbackFn = self.pings[ping.id]
            try:
                callbackFn(msg.srcId, recv-sent)
            except Exception, exc:
                logger.exception(exc)
            del self.pings[ping.id]
    def _checkTimeout(self, pingId, dstId):
        if not pingId in self.pings:
            return
        _, callbackFn = self.pings[pingId]
        try:
            callbackFn(dstId, None)
        except Exception, exc:
            logger.exception(exc)
        del self.pings[pingId]
    def ping(self, dstId, callback, timeout=300.0):
        pingId = random.randint(1, 2**16)
        while pingId in self.pings:
            pingId = random.randint(1, 2**16)
        self.pings[pingId] = (time.time(), callback)
        self.node.send(dstId=dstId, pingMsg=proto.PingMessage(type=proto.PingMessage.PING, id=pingId)) #@UndefinedVariable
        timer.schedule(self._checkTimeout, timeout, args=[pingId, dstId])