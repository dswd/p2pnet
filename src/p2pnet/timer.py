
import time, logging

logger = logging.getLogger(__name__)

class TimerTask:
  def __init__(self, task, args, kwargs, timeout, nextTime, repeated, strict):
    self.task = task
    self.args = args
    self.kwargs = kwargs
    self.timeout = timeout
    self.nextTime = nextTime
    self.repeated = repeated
    self.strict = strict

tasks = []

def schedule(func, timeout, repeated=False, strict=False, args=[], kwargs={}):
  _schedule(TimerTask(task=func, args=args, kwargs=kwargs, timeout=timeout, nextTime=time.time()+timeout, repeated=repeated, strict=strict))

def _schedule(task):
  tasks.append(task)
  tasks.sort(key=lambda t: t.nextTime)
  
def check():
  while tasks and time.time() > tasks[0].nextTime:
    t = tasks[0]
    tasks.remove(t)
    try:
      t.task(*t.args, **t.kwargs)
    except Exception, exc:
      logger.exception(exc)
    if t.repeated:
      if t.strict:
        t.nextTime += t.timeout
      else:
        t.nextTime = time.time() + t.timeout
      _schedule(t)

def nextTimeout():
  return (tasks[0].nextTime - time.time()) if tasks else None
      
def run():
  while True:
    check()
    if tasks:
      time.sleep(tasks[0].nextTime - time.time())
    else:
      time.sleep(1.0)