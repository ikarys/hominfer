"""Model supervisor: start / stop models, and every few seconds a snapshot of their state and
usage (VRAM, RAM, CPU) for the page.

Models started here are stopped when the launcher stops. An engine started outside the launcher
is detected by its process names, and can be stopped too.
"""
import os
import shlex
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import psutil

from ..domain import engine as engine_rules
from ..domain import events as event_rules
from ..domain import restart as restart_rules
from ..domain import sessions as session_rules
from ..domain.model import clean_options
from ..domain.status import baseline_ok, model_state, model_vram, on_gpu_for
from ..errors import LaunchError
from ..i18n import gib, tr
from ..infra import net, processes
from ..infra.files import cap_log, tail

LOG_CAP = 50 * 2**20  # a running model's log is emptied past this size


class Supervisor:
    def __init__(self, registry, updates, *, gpu, keep_awake, log_dir, models_dir, default_baseline_mib,
                 gpu_mem=None, engine_metrics=None, win_gpu=None, events=None):
        """gpu: () -> GPU state or None; keep_awake: .set(bool) holds off the host's sleep;
        models_dir: () -> the models folder (a setting);
        gpu_mem: (pids, pdev, unified) -> {pid: MiB}, the per-process GPU memory when the driver gives it (AMD);
        engine_metrics: .collect(ids) -> {id: metrics} of the engines that expose some;
        win_gpu: () -> [{name, bytes}] GPU memory reserved by Windows processes (WSL), or None;
        events: the EventLog that gets what changed between two polls and the start / stop requests."""
        self.registry, self.updates, self.gpu, self.keep_awake = registry, updates, gpu, keep_awake
        self.gpu_mem, self.engine_metrics, self.win_gpu, self.events = gpu_mem, engine_metrics, win_gpu, events
        self.log_dir, self.models_dir, self.default_baseline_mib = log_dir, models_dir, default_baseline_mib
        self.lock = threading.RLock()
        self.poll_lock = threading.Lock()  # the loop and the HTTP actions both poll
        self.cpu_last = {}   # pid or "machine" -> (time, %): cpu_percent over a few ms is noise
        self.last_gpu = None  # the poll's GPU state: requests read it instead of re-running nvidia-smi
        self.runs = {}       # started from here: id -> {popen, opts, vram_before, vram_load}
        self.errors = {}     # id -> message
        self.stopping = set()
        self.restarts = {}   # id -> epoch times of its automatic restarts
        self.sessions = {}   # id -> concurrent sessions seen since the model started (domain/sessions)
        self.baseline = None  # VRAM used with no model, once seen
        self.pcache = {}     # pid -> psutil.Process (cpu_percent needs its history)
        self.snapshot = {"ready": False}
        self.ip = net.lan_ip()
        log_dir.mkdir(parents=True, exist_ok=True)

    def baseline_mib(self):
        return self.baseline if self.baseline is not None else self.default_baseline_mib

    def find(self):
        return processes.find(self.registry.process_patterns())

    def is_running(self, mid):
        return bool(self.find().get(mid))

    def log(self, mid):
        return tail(self.log_dir / f"{mid}.log")

    # -- measures
    def run_forever(self, interval):
        while True:
            try:
                self.poll()
            except Exception as e:  # the page must keep answering
                print("poll:", e, file=sys.stderr)
            time.sleep(interval)

    def gpu_cached(self):
        """The GPU state of the last poll (<= one interval old); start() still queries it fresh."""
        return self.last_gpu if self.snapshot["ready"] else self.gpu()

    def poll(self):
        with self.poll_lock:
            self._poll()

    def _probe(self, procs):
        """Health checks of the running models, in parallel and outside self.lock (start/stop stay responsive)."""
        models = self.registry.models  # a reload swaps the dict: keep one view
        up = [(mid, models[mid]) for mid, ps in procs.items() if ps and mid in models]
        if not up:
            return {}
        with ThreadPoolExecutor(len(up)) as ex:
            ok = ex.map(lambda m: net.http_ok(m["port"], m["health"]), (m for _, m in up))
            return dict(zip((mid for mid, _ in up), ok))

    def _poll(self):
        gpu, procs = self.gpu(), self.find()
        for mid in (mid for mid, ps in procs.items() if ps):
            cap_log(self.log_dir / f"{mid}.log", LOG_CAP)
        healthy = self._probe(procs)
        running = any(procs.values())
        metrics = self.engine_metrics.collect([mid for mid, ok in healthy.items() if ok]) if self.engine_metrics else {}
        samples = self.engine_metrics.samples() if self.engine_metrics else {}
        mem = self._gpu_mem(gpu, procs)
        if mem is not None:  # measured per process: everything else is the baseline
            self.baseline = max(0, gpu["used"] - sum(mem.values()))
            on_gpu = {mid: v > 64 for mid, v in mem.items()}
        else:
            if gpu and baseline_ok(gpu["pids"], running, gpu["util"]):
                self.baseline = gpu["used"]
            # A model on the GPU keeps its VRAM while the process lives, even when the GPU is idle
            # (util ~ 0): attribute the GPU to VRAM allocated beyond the idle baseline, not to the
            # instantaneous activity (which flickers with every request).
            allocated = bool(gpu) and (gpu["used"] - self.baseline_mib()) > 256
            on_gpu = on_gpu_for(procs, gpu["pids"], allocated) if gpu else {mid: False for mid in procs}
        with self.lock:
            for mid, sample in samples.items():
                session_rules.record(self.sessions.setdefault(mid, session_rules.new_stats()), sample, time.time())
            models = {mid: self._model_view(mid, m, procs.get(mid, []), gpu, on_gpu, healthy.get(mid, False),
                                            mem and mem.get(mid)) | ({"metrics": metrics[mid]} if mid in metrics else {})
                      | {"sessions": session_rules.summary(self.sessions[mid]) if mid in self.sessions else None}
                      for mid, m in self.registry.models.items()}
            alive = {p.pid for ps in procs.values() for p in ps}
            self.pcache = {pid: p for pid, p in self.pcache.items() if pid in alive}
            self.cpu_last = {k: v for k, v in self.cpu_last.items() if k in alive or k == "machine"}
        # the VM's own memory under WSL: its cap (.wslconfig), not the host's RAM, bounds a model
        vm = psutil.virtual_memory()
        ram = {"used_mib": round((vm.total - vm.available) / 2**20), "total_mib": round(vm.total / 2**20)}
        self.last_gpu = gpu
        win = self.win_gpu() if self.win_gpu else None
        prev = self.snapshot
        self.snapshot = {
            "ready": True, "time": time.time(), "lan_ip": self.ip,
            "gpu": gpu and {k: v for k, v in gpu.items() if k not in ("pids", "pdev")} | {
                "baseline": self.baseline_mib(), "baseline_measured": self.baseline is not None}
            | ({"processes": win} if win else {}),
            "ram": ram,
            "cpu": {"pct": self._cpu("machine", psutil.cpu_percent), "count": psutil.cpu_count() or 1},
            "models": models,
        }
        self.keep_awake.set(any(v["pids"] for v in models.values()))
        if self.events:
            names = {mid: m["name"] for mid, m in self.registry.models.items()}
            self.events.extend(event_rules.diff(prev, self.snapshot, self.snapshot["time"], names))

    def _gpu_mem(self, gpu, procs):
        """{model id: GPU memory in MiB} when the driver reports it per process, else None."""
        if not (gpu and self.gpu_mem and gpu.get("pdev")):
            return None
        by_pid = self.gpu_mem([p.pid for ps in procs.values() for p in ps], gpu["pdev"], gpu["unified"])
        return {mid: sum(by_pid.get(p.pid, 0) for p in ps) for mid, ps in procs.items()}

    def _model_view(self, mid, m, ps, gpu, on_gpu, healthy, mem_mib=None):
        self._watch(mid, ps, healthy)
        run = self._check_exit(mid, ps)
        state = model_state(stopping=mid in self.stopping, running=bool(ps), failed=mid in self.errors,
                            healthy=bool(ps) and healthy)
        if state == "ready" and run and run["vram_load"] is None and gpu and run["vram_before"] is not None:
            run["vram_load"] = max(0, gpu["used"] - run["vram_before"])
        vram, how = None, None
        if ps and mem_mib is not None:
            vram, how = (mem_mib, "live") if on_gpu.get(mid) else (0, "cpu")
        elif ps and gpu:
            vram, how = model_vram(mid, on_gpu, gpu["used"], self.baseline_mib(), self.baseline is not None,
                                   run and run["vram_load"], pids_known=bool(gpu["pids"]))
        rss, cpu, started = self._usage(ps)
        ncpu = psutil.cpu_count() or 1
        return {
            "state": state, "managed": run is not None, "error": self.errors.get(mid),
            "pids": [p.pid for p in ps], "on_gpu": on_gpu.get(mid, False), "vram_mib": vram, "vram_how": how,
            "rss_mib": round(rss / 2**20) if ps else None,
            "cpu_pct": round(cpu, 1) if ps else None,  # 100 = one core
            "cpu_machine_pct": round(cpu / ncpu, 1) if ps else None,
            "uptime_s": round(time.time() - started) if started else None,
            "opts": run["opts"] if run else None,
            "cmdlines": self._cmdlines(ps, m.get("procs", [])),
            "env": run["env"] if run else None,
            "engine_behind": self.updates.behind(m["engine_id"]),
        }

    def _watch(self, mid, ps, healthy):
        """Restart (in a thread) a model started here that died or stopped answering after being ready."""
        run = self.runs.get(mid)
        if not run or mid in self.stopping or not self.registry.engines[self.registry.models[mid]["engine_id"]].get("restart", True):
            return
        now = time.time()
        hist = self.restarts[mid] = [t for t in self.restarts.get(mid, []) if now - t < 3600]
        v = restart_rules.verdict(run["watch"], alive=bool(ps), healthy=healthy, history=hist, now=now)
        if v == "restart":
            hist.append(now)
            self.stopping.add(mid)
            self._log("warn", "restarted", mid)
            threading.Thread(target=self._restart, args=(mid, ps, run["opts"]), daemon=True).start()
        elif v:
            self._log("alarm", "restart_gave_up", mid)

    def _restart(self, mid, procs, opts):
        self._kill(mid, procs)
        try:
            self.start(mid, opts)
        except LaunchError as e:
            with self.lock:
                self.errors[mid] = str(e)

    def _check_exit(self, mid, ps):
        """The run of a model started here, forgotten (with an error) if it died by itself."""
        run = self.runs.get(mid)
        if run and run["popen"].poll() is not None and mid not in self.stopping and not ps:
            self.errors[mid] = tr("run.died", code=run["popen"].returncode)
            self.runs.pop(mid)
            return None
        return run

    def _cpu(self, key, measure):
        """measure() = % since its previous call: an HTTP action polling right after the loop
        would get a ~0 ms window, so a measure younger than 1 s is reused instead."""
        now, last = time.monotonic(), self.cpu_last.get(key)
        if last and now - last[0] < 1:
            return last[1]
        self.cpu_last[key] = (now, measure(None))
        return self.cpu_last[key][1]

    def _usage(self, ps):
        rss, cpu, started = 0, 0.0, None
        for p in ps:
            cp = self.pcache.setdefault(p.pid, p)
            try:
                with cp.oneshot():
                    rss += cp.memory_info().rss
                    cpu += self._cpu(p.pid, cp.cpu_percent)
                    created = cp.create_time()
                    started = created if started is None else min(started, created)
            except psutil.Error:
                pass
        return rss, cpu, started

    def _cmdlines(self, ps, procs):
        """Redacted command lines of the engine's own processes (workers are skipped)."""
        out = []
        wanted = set(procs or [])
        for p in ps:
            try:
                cmdline = p.cmdline()
            except psutil.Error:
                continue
            if not cmdline:
                continue
            names = {os.path.basename(cmdline[0])}
            if len(cmdline) > 1:
                names.add(os.path.basename(cmdline[1]))
            if not names & wanted:
                continue
            argv, _ = engine_rules.redact(cmdline)
            out.append(shlex.join(argv))
        return out

    # -- actions
    def _command(self, mid, clean, free):
        m = self.registry.models[mid]
        return engine_rules.build_command(
            self.registry.engines[m["engine_id"]], mid, m["config"], m["fixed"] | clean,
            vram_need=m["vram_mib"], free_vram=free, models_dir=self.models_dir())

    def start(self, mid, opts):
        m = self.registry.models[mid]
        with self.lock:
            if self.is_running(mid):
                raise LaunchError(tr("run.already"))
            for port, who in m["conflicts"].items():
                if net.port_open(port):
                    raise LaunchError(tr("run.conflict", who=who, port=port))
            if net.port_open(m["port"]):
                raise LaunchError(tr("run.port_busy", port=m["port"]))
            clean = clean_options(m, opts)
            gpu = self.gpu()
            free = gpu["total"] - gpu["used"] if gpu else 0
            argv, env, need = self._command(mid, clean, free)
            if gpu and need and free < need:
                self._refuse_no_vram(mid, free, need)
            header = f"$ {' '.join(argv)}\n  {' '.join(f'{k}={v}' for k, v in env.items())}\n\n"
            popen = processes.spawn(argv, self.log_dir / f"{mid}.log", env=env, header=header)
            self.runs[mid] = {
                "popen": popen, "opts": clean, "env": engine_rules.redact([], env)[1],
                "vram_before": gpu and gpu["used"], "vram_load": None, "watch": restart_rules.new_watch(),
            }
            self.errors.pop(mid, None)
            self.sessions[mid] = session_rules.new_stats()
            self._log("run", "start_req", mid)

    def preview(self, mid, opts):
        """The command hominfer would launch, with secrets masked (no VRAM check, no spawn)."""
        gpu = self.gpu_cached()  # no nvidia-smi run per option change
        argv, env, _ = self._command(mid, clean_options(self.registry.models[mid], opts),
                                     gpu["total"] - gpu["used"] if gpu else 0)
        argv, env = engine_rules.redact(argv, env)
        return {"argv": shlex.join(argv), "env": env}

    def _log(self, level, key, mid):
        if self.events:
            self.events.add(level, key, mid, name=self.registry.models[mid]["name"])

    def _refuse_no_vram(self, mid, free, need):
        others = [self.registry.models[o]["name"] for o, s in self.snapshot.get("models", {}).items()
                  if o != mid and s.get("on_gpu") and o in self.registry.models]
        hint = tr("run.no_vram_hint", models=", ".join(others)) if others else ""
        raise LaunchError(tr("run.no_vram", free=gib(free), need=gib(need), hint=hint))

    def stop(self, mid):
        with self.lock:
            procs = self.find().get(mid, [])
            self.errors.pop(mid, None)
            if not procs:
                self.runs.pop(mid, None)
                return
            self.stopping.add(mid)
            self._log("info", "stop_req", mid)
        threading.Thread(target=self._kill, args=(mid, procs), daemon=True).start()

    def _kill(self, mid, procs):
        run = self.runs.get(mid)
        try:
            if run:  # the whole group: e.g. an engine's watchdog script and its "sleep"
                processes.kill_group(run["popen"])
            processes.terminate(procs)
            if run:
                try:
                    run["popen"].wait(5)
                except Exception:
                    pass
        finally:
            with self.lock:
                self.runs.pop(mid, None)
                self.stopping.discard(mid)

    def shutdown(self):
        """Stop the models started here (the launcher is stopping)."""
        with self.lock:
            mine = list(self.runs)
        for mid in mine:
            procs = self.find().get(mid, [])
            if procs:
                print(f"stopping {mid}...", flush=True)
                self.stopping.add(mid)
                self._kill(mid, procs)
