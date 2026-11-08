"""Usage history: hourly buckets per model (time up, busy seconds per number of requests running
at once, peaks), and their aggregation over a time range, globally, per model and per engine."""

HOUR = 3600
KEEP_S = 90 * 86400


def key(hour, mid):
    """Build the row key for an hour and model."""
    return f"{hour} {mid}"


def _is_number(value):
    """Return True for int/float values, excluding bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _clean_busy(busy):
    """Keep only digit level keys with numeric seconds."""
    out = {}
    if not isinstance(busy, dict):
        return out
    for level, seconds in busy.items():
        if not isinstance(level, str) or not level.isdigit():
            continue
        if not _is_number(seconds):
            continue
        if int(level) < 1:
            continue
        out[level] = float(seconds)
    return out


def _clean_int(value):
    """Return an int for numeric values, else None."""
    if _is_number(value):
        return int(round(value))
    return None


def index(items):
    """Turn raw JSON rows into a keyed row dict."""
    rows = {}
    if not isinstance(items, list):
        return rows
    for item in items:
        if not isinstance(item, dict):
            continue
        hour = item.get("hour")
        mid = item.get("model")
        engine = item.get("engine")
        if not isinstance(hour, int) or isinstance(hour, bool):
            continue
        if not isinstance(mid, str) or not isinstance(engine, str):
            continue
        up = item.get("up")
        if not _is_number(up):
            up = 0.0
        row = {
            "hour": hour,
            "model": mid,
            "engine": engine,
            "up": float(up),
            "busy": _clean_busy(item.get("busy")),
            "peak": _clean_int(item.get("peak")),
            "peak_waiting": _clean_int(item.get("peak_waiting")),
            "limit": _clean_int(item.get("limit")),
        }
        rows[key(hour, mid)] = row
    return rows


def credit(rows, now, dt, mid, engine, sample):
    """Add one poll (dt seconds) of model `mid`, up on `engine`; sample: the session gauges or None."""
    hour = int(now // HOUR * HOUR)
    row = rows.setdefault(key(hour, mid), {"hour": hour, "model": mid, "engine": engine, "up": 0.0, "busy": {},
                                           "peak": None, "peak_waiting": None, "limit": None})
    row["engine"] = engine
    row["up"] += dt
    sample = sample or {}
    if sample.get("running") is not None:
        level = max(0, int(round(sample["running"])))
        if level > 0 and dt > 0:
            row["busy"][str(level)] = row["busy"].get(str(level), 0.0) + dt
        row["peak"] = max(row["peak"] or 0, level)
    if sample.get("waiting") is not None:
        row["peak_waiting"] = max(row["peak_waiting"] or 0, int(round(sample["waiting"])))
    if sample.get("limit") is not None:
        row["limit"] = int(round(sample["limit"]))


def prune(rows, now):
    """Drop rows older than the retention window."""
    for k in [k for k, r in rows.items() if r["hour"] < now - KEEP_S]:
        del rows[k]


def _max(values):
    values = [v for v in values if v is not None]
    return max(values) if values else None


def summary(rows_list):
    """Sum rows: up and busy seconds, peaks, and the busy time's split by number of requests running at once."""
    levels = {}
    for row in rows_list:
        for level, seconds in row["busy"].items():
            levels[int(level)] = levels.get(int(level), 0.0) + seconds
    busy = sum(levels.values())
    return {"up": round(sum(r["up"] for r in rows_list)), "busy": round(busy),
            "peak": _max(r["peak"] for r in rows_list), "peak_waiting": _max(r["peak_waiting"] for r in rows_list),
            "limit": _max(r["limit"] for r in rows_list),
            "share": [[lv, round(s / busy, 3)] for lv, s in sorted(levels.items())] if busy else []}


def _group(rows_list, field):
    out = {}
    for row in rows_list:
        out.setdefault(row[field], []).append(row)
    return out


def aggregate(rows, start, end):
    """Rows overlapping [start, end): total, per model, per engine, and per hour (summed over models)."""
    selected = [r for r in rows.values() if start - HOUR < r["hour"] < end]
    models = {mid: summary(rs) | {"engine": max(rs, key=lambda r: r["hour"])["engine"]}
              for mid, rs in _group(selected, "model").items()}
    hours = [[h, _max(r["peak"] for r in rs), round(sum(sum(r["busy"].values()) for r in rs)),
              round(sum(r["up"] for r in rs))] for h, rs in sorted(_group(selected, "hour").items())]
    return {"total": summary(selected), "models": models,
            "engines": {e: summary(rs) for e, rs in _group(selected, "engine").items()}, "hours": hours}
