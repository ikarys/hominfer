"""Events: what changed between two status snapshots (the dict the supervisor builds in _poll).

An event is {"t": epoch seconds, "level": info | run | warn | alarm, "key": locale key, "args": {...},
"model": id or None}; the page renders the text from the key. Pure: the caller gives the time and names.
"""
VRAM_HIGH_PCT = 90
PREEMPTIONS = "preemptions"  # the `event` tag of an engine metric (engines.json `metrics.show`)


def event(now, level, key, model=None, **args):
    return {"t": now, "level": level, "key": "ui.ev." + key, "args": args, "model": model}


def _vram_pct(snap):
    g = snap.get("gpu")
    return g and g["total"] and g["used"] / g["total"] * 100


def _win_over(snap):
    """GPU memory reserved by Windows processes goes beyond the card (Windows then pages it out)."""
    g = snap.get("gpu")
    return bool(g and sum(p["bytes"] for p in g.get("processes", [])) / 2**20 > g["total"])


def _preemptions(model):
    """The engine's preemption counter, or None when the model exposes none."""
    found = [i["value"] for i in model.get("metrics", []) if i.get("event") == PREEMPTIONS]
    return sum(found) if found else None


def _model_events(now, mid, name, old, new):
    """old: the model's previous view, or None when it was not there."""
    was, state = old["state"] if old else "stopped", new["state"]
    out = []
    if was in ("stopped", "error") and state in ("starting", "ready"):
        out.append(event(now, "run", "started", mid, name=name))
    if state == "ready" and was != "ready":
        out.append(event(now, "run", "ready", mid, name=name))
    if state == "stopped" and was in ("starting", "ready", "stopping"):
        out.append(event(now, "info", "stopped", mid, name=name))
    if state == "error" and was != "error":
        out.append(event(now, "alarm", "crashed", mid, name=name, detail=new.get("error") or ""))
    if was == "ready" and state == "starting":  # the process lives but the health check fails
        out.append(event(now, "alarm", "health", mid, name=name))
    before, after = _preemptions(old or {}), _preemptions(new)
    if before is not None and after is not None and after > before:
        out.append(event(now, "warn", "preempt", mid, name=name, n=round(after - before)))
    return out


def diff(prev, new, now, names=None):
    """-> the events that `new` brings over `prev` (both snapshots; nothing before the first real one).
    names: {model id: display name}."""
    if not (prev and prev.get("ready") and new.get("ready")):
        return []
    names, out = names or {}, []
    for mid, view in new["models"].items():
        out += _model_events(now, mid, names.get(mid, mid), prev["models"].get(mid), view)
    a, b = _vram_pct(prev), _vram_pct(new)
    if a is not None and b is not None:
        g = new["gpu"]
        if a <= VRAM_HIGH_PCT < b:
            out.append(event(now, "warn", "vram_high", pct=round(b), used=g["used"], total=g["total"]))
        elif b <= VRAM_HIGH_PCT < a:
            out.append(event(now, "info", "vram_ok", pct=round(b)))
    if prev.get("gpu") and new.get("gpu"):
        if _win_over(new) and not _win_over(prev):
            out.append(event(now, "warn", "win_over"))
        elif _win_over(prev) and not _win_over(new):
            out.append(event(now, "info", "win_ok"))
    return out
