"""The event log: a ring buffer of what happened (models started / stopped / crashed, memory alarms,
updates...), read by the page with GET /api/events?since=<id>. In memory only, lost at restart."""
import threading
import time
from collections import deque

from ..domain.events import event

MAX_EVENTS = 300


class EventLog:
    def __init__(self, maxlen=MAX_EVENTS):
        self.lock = threading.Lock()
        self.items = deque(maxlen=maxlen)
        self.last = 0  # id of the newest event; ids only grow

    def add(self, level, key, model=None, **args):
        """Push one event now (key: a ui.ev.* locale key without its prefix)."""
        self.extend([event(time.time(), level, key, model, **args)])

    def extend(self, events):
        """Push events as built by domain.events (they get their id here)."""
        with self.lock:
            for e in events:
                self.last += 1
                self.items.append(e | {"id": self.last})

    def since(self, last_seen=0):
        """{"events": the events with an id above last_seen (oldest first), "last": newest id}."""
        with self.lock:
            return {"events": [e for e in self.items if e["id"] > last_seen], "last": self.last}
