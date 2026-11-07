"""Engine metrics: parse Prometheus text exposition and evaluate the `metrics.show` items of an engine.

An EXPR is `name` or `name{k="v",k2="v2"}`: it selects the samples that have at least those labels,
and their values are summed. No sample selected -> no value.
"""
import math
import re

UNITS = ("count", "bytes", "pct", "x")
MAX_ITEMS = 16
MAX_LABEL = 60
_NAME = r"[a-zA-Z_:][a-zA-Z0-9_:]*"
_PAIR = re.compile(r'\s*(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"\s*(?:,|$)')
# a label value is quoted: braces and commas inside it do not end the label set
_LINE = re.compile(rf'({_NAME})(?:\{{((?:[^"}}]|"(?:[^"\\]|\\.)*")*)\}})?\s+(\S+)')
EXPR = re.compile(rf'{_NAME}(?:\{{\s*\w+="[^"\\]*"\s*(?:,\s*\w+="[^"\\]*"\s*)*\}})?')
_ESC = re.compile(r"\\(.)")


def _labels(body):
    return {k: _ESC.sub(lambda m: "\n" if m[1] == "n" else m[1], v) for k, v in _PAIR.findall(body or "")}


def parse(text):
    """Prometheus text -> [(name, labels, value)]. Comments, malformed lines, NaN / Inf are skipped;
    a timestamp after the value is ignored."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        m = line and not line.startswith("#") and _LINE.match(line)
        if not m:
            continue
        try:
            v = float(m[3])
        except ValueError:
            continue
        if math.isfinite(v):
            out.append((m[1], _labels(m[2]), v))
    return out


def select(samples, expr):
    """Sum of the samples matching EXPR, or None when none matches."""
    name, _, rest = expr.partition("{")
    want = _labels(rest.rstrip("}"))
    hits = [v for n, lab, v in samples if n == name and all(lab.get(k) == x for k, x in want.items())]
    return sum(hits) if hits else None


def _value(item, samples):
    if "value" in item:
        return select(samples, item["value"])
    a, b = (select(samples, e) for e in item["ratio"])
    if a is None or not b:
        return None
    return 1 - a / b if item.get("one_minus") else a / b


def evaluate(show, samples, *, loc=str):
    """-> [{"label", "value", "unit"}], the items with a value only. loc: label text (str or {lang: text})."""
    out = []
    for item in show:
        v = _value(item, samples)
        if v is not None:
            out.append({"label": loc(item["label"]), "value": v, "unit": item.get("unit", "count")})
    return out


def _label_ok(x):
    return isinstance(x, str) and 0 < len(x) <= MAX_LABEL


def _item_ok(i):
    if not isinstance(i, dict):
        return False
    lab = i.get("label")
    if not (_label_ok(lab) or isinstance(lab, dict) and lab and all(_label_ok(v) for v in lab.values())):
        return False
    if ("value" in i) == ("ratio" in i) or i.get("unit", "count") not in UNITS:
        return False
    if "value" in i:
        exprs = [i["value"]]
    else:
        exprs = i["ratio"]
        if not (isinstance(exprs, list) and len(exprs) == 2):
            return False
    return all(isinstance(e, str) and EXPR.fullmatch(e) for e in exprs)


def valid_show(show):
    """True when `metrics.show` is well formed (see docs/configuration.md)."""
    return isinstance(show, list) and 0 < len(show) <= MAX_ITEMS and all(_item_ok(i) for i in show)
