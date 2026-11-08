"""Concurrent sessions of a model, from polled engine gauges: peaks, and how the busy time splits
between 1, 2, 3... requests running at once (to size the engine's max concurrency)."""
from .metrics import EXPR

MAX_GAP_S = 30

def new_stats():
    """-> empty accumulator (a plain dict, JSON-able)."""
    return {"prev_time": None, "prev_running": None, "peak": 0, "peak_waiting": None, "limit": None, "seconds": {}}

def record(stats, sample, now):
    """Add one poll."""
    running = sample.get("running")
    if running is None:
        stats["prev_time"] = None
        stats["prev_running"] = None
        return

    level = max(0, int(round(running)))
    prev_time = stats["prev_time"]
    if prev_time is not None:
        gap = now - prev_time
        if 0 < gap <= MAX_GAP_S:
            stats["seconds"][stats["prev_running"]] = stats["seconds"].get(stats["prev_running"], 0) + gap

    stats["prev_time"] = now
    stats["prev_running"] = level
    stats["peak"] = max(stats["peak"], level)

    waiting = sample.get("waiting")
    if waiting is not None:
        waiting = max(0, int(round(waiting)))
        stats["peak_waiting"] = max(stats["peak_waiting"] or 0, waiting)

    limit = sample.get("limit")
    if limit is not None:
        stats["limit"] = max(0, int(round(limit)))

def summary(stats):
    """-> None until some busy time was measured, else {"peak", "peak_waiting", "limit",
    "share": [[level, fraction of the busy time], ...]}; idle time (level 0) is left out."""
    seconds = {k: v for k, v in stats["seconds"].items() if k > 0}
    total = sum(seconds.values())
    if total == 0:
        return None

    share = []
    for level in sorted(seconds):
        sec = seconds[level]
        if sec > 0:
            share.append([level, round(sec / total, 3)])

    return {"peak": stats["peak"], "peak_waiting": stats["peak_waiting"], "limit": stats["limit"], "share": share}

def valid_spec(spec):
    """True when the engines.json `metrics.sessions` block is well formed."""
    if not isinstance(spec, dict) or "running" not in spec:
        return False
    if not set(spec).issubset({"running", "waiting", "limit"}):
        return False
    return all(isinstance(value, str) and EXPR.fullmatch(value) is not None for value in spec.values())
