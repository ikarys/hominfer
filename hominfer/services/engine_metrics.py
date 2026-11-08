"""Engine metrics of the running models (engines.json `metrics`): fetched from the engine's
Prometheus endpoint, evaluated (plus the `sessions` gauges), cached a few seconds so the page's polling doesn't hammer the engine."""
import time
from concurrent.futures import ThreadPoolExecutor

from ..domain import metrics
from ..i18n import loc
from ..infra import net

TTL_S = 5


class EngineMetrics:
    def __init__(self, registry, fetch=net.http_text):
        """fetch: (port, path) -> text or None."""
        self.registry, self.fetch = registry, fetch
        self.cache = {}  # model id -> (time, items, sessions sample)

    def collect(self, mids):
        """{model id: items} for those of `mids` whose engine has metrics and answers. Never raises;
        a failing endpoint costs one timeout per TTL, not per poll."""
        models, engines = self.registry.models, self.registry.engines
        todo = {mid: (models[mid]["port"], engines[models[mid]["engine_id"]]["metrics"]) for mid in mids
                if mid in models and "metrics" in engines.get(models[mid]["engine_id"], {})}
        now = time.monotonic()
        stale = [mid for mid in todo if mid not in self.cache or now - self.cache[mid][0] >= TTL_S]
        if stale:
            with ThreadPoolExecutor(len(stale)) as ex:
                for mid, read in zip(stale, ex.map(lambda mid: self._read(*todo[mid]), stale)):
                    self.cache[mid] = (now, *read)
        self.cache = {mid: v for mid, v in self.cache.items() if mid in todo}
        return {mid: self.cache[mid][1] for mid in todo if self.cache[mid][1]}

    def samples(self):
        """{model id: {"running", "waiting", "limit"}} read by the last collect, for engines with `sessions`."""
        return {mid: c[2] for mid, c in self.cache.items() if c[2]}

    def _read(self, port, spec):
        try:
            text = self.fetch(port, spec["path"])
            if not text:
                return [], None
            samples = metrics.parse(text)
            sessions = {k: metrics.select(samples, e) for k, e in spec.get("sessions", {}).items()} or None
            return metrics.evaluate(spec["show"], samples, loc=loc), sessions
        except Exception:
            return [], None
