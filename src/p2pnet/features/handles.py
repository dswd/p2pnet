'''
Created on Jan 11, 2013

@author: schwerdel
'''

import random, logging

from ..base import Event
from .. import proto

logger = logging.getLogger(__name__)

Event.TYPE_HANDLE_UNBOUND = "handle_unbound"

class Feature:
    def __init__(self, node):
        self.node = node
        self.handles = {}
        node.addListener(self._handleEvent)
        node.bindHandle = self.bindHandle
        node.isHandleBound = self.isHandleBound
    def _handleEvent(self, evt):
        if evt.getType() != Event.TYPE_MESSAGE_ROUTED:
            return
        msg = evt.getData()
        for ctrl in msg.routedControl:
            if ctrl.code == proto.Control.Routing_UnboundHandle: #@UndefinedVariable
                self.node._event(type=Event.TYPE_HANDLE_UNBOUND, node=msg.srcId, data=ctrl.number[0]) #@UndefinedVariable
        if not msg.hasField("dstHandle"):
            return
        if self.isHandleBound(msg.dstHandle):
            try:
                self.handles.get(msg.dstHandle)(msg)
            except Exception, exc:
                logger.exception(exc)
        elif not msg.routedControl:
            self.node._routedError(msg.srcId, proto.Control.ERROR, proto.Control.Routing_UnboundHandle, number=[msg.dstHandle or 0]) #@UndefinedVariable
    def bindHandle(self, handleFn, handleId=None):
        if handleFn:
            if not handleId:
                handleId = random.randint(1, 2**16)
            self.handles[handleId] = handleFn
            return handleId
        elif self.isHandleBound(handleId):
            del self.handles[handleId]
    def isHandleBound(self, handleId):
        return handleId in self.handles