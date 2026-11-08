"""The usage history on disk (one JSON file, saved every minute and pruned to 90 days): fed by the
supervisor's poll, read by GET /api/stats."""

import json
import threading

from ..domain import stats as rules
from ..domain.sessions import MAX_GAP_S
from ..infra.files import read_json, write_atomic


class StatsHistory:
    """Persistent usage history with thread-safe observe/save/query."""

    def __init__(self, path, save_every=60):
        """Load history from path and prepare polling state."""
        self.path = path
        self.save_every = save_every
        self.lock = threading.Lock()
        try:
            items = read_json(path, [])
        except (OSError, ValueError):
            items = []
        if not isinstance(items, list):
            items = []
        self.rows = rules.index(items)
        self.last = None
        self.saved = None

    def observe(self, now, up):
        """Credit one poll of the models currently up."""
        with self.lock:
            if self.last is not None and 0 < now - self.last <= MAX_GAP_S:
                dt = now - self.last
            else:
                dt = 0
            self.last = now
            for mid, (engine, sample) in up.items():
                rules.credit(self.rows, now, dt, mid, engine, sample)
            if self.saved is None:
                self.saved = now
            elif now - self.saved >= self.save_every:
                self.save(now)

    def save(self, now):
        """Prune and write the current rows to disk."""
        try:
            rules.prune(self.rows, now)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            write_atomic(self.path, json.dumps(list(self.rows.values()), separators=(",", ":")))
        except OSError:
            pass
        self.saved = now

    def flush(self, now):
        """Save the current rows under the lock."""
        with self.lock:
            self.save(now)

    def query(self, start, end):
        """Return aggregated stats for a time range."""
        with self.lock:
            return rules.aggregate(self.rows, start, end) | {"from": start, "to": end}
