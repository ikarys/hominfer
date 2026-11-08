"""Engine catalog (catalog/): known engines, installed in the background from the page.

Each engine has an idempotent install script in ~/llm/<engine> (running it again updates /
reconfigures). The page only picks a catalog id: scripts come from the repository. Once
installed, the engine's block is added to engines.json if its id is free.
"""
import json
from pathlib import Path

from ..domain.engine import expand
from ..domain.prereqs import fix_commands
from ..errors import LaunchError
from ..i18n import loc, tr
from ..infra import prereqs
from ..infra.engine_files import is_installed
from .jobs import Jobs


class Catalog:
    def __init__(self, catalog_dir, registry, log_dir, models_dir):
        """models_dir: () -> the models folder (engines fetching their own weights put them there)."""
        self.dir, self.registry, self.log_dir, self.models_dir = catalog_dir, registry, log_dir, models_dir
        self.entries = json.loads((catalog_dir / "catalog.json").read_text())
        reqs = json.loads((catalog_dir / "requirements.json").read_text())
        self.reqs = {**reqs["tools"], **reqs["libraries"]}
        self.jobs = Jobs()

    def state(self, cid):
        """configured: in engines.json and installed | present: on disk (maybe partly) | available"""
        c = self.entries[cid]
        if cid in self.registry.engines and self.registry.installed(cid):
            return "configured"
        found = is_installed(c["engine"]) or c.get("detect") and (Path(expand(c["dir"])) / c["detect"]).exists()
        return "present" if found else "available"

    def compat(self, cid, gpu):
        """gpu: {"vendor", "cc"...} or None. "gpu" lists the vendors a recipe builds for (none: any)."""
        c, vendor, cc = self.entries[cid], gpu and gpu.get("vendor"), gpu and gpu.get("cc")
        if c.get("gpu") and vendor not in c["gpu"]:
            return False, tr("eng.gpu_vendor", vendors=" / ".join(v.upper() for v in c["gpu"]))
        if c.get("min_cc") and (cc or 0) < c["min_cc"]:
            return False, tr("eng.min_cc", cc=c["min_cc"], gpu_cc=cc)
        return True, ""

    def missing(self, cid):
        return [n for n in self.entries[cid].get("requires", []) if not prereqs.present(self.reqs[n])]

    def suggest(self, fmt, kind, repo, gpu):
        """Catalog engine that would run this model, if it isn't set up yet."""
        for cid, c in self.entries.items():
            e = c["engine"]
            runs = repo in e.get("provides_repos", []) or (
                f".{fmt}" in e.get("file_ext", []) and (kind is None or kind in e.get("kinds", [kind])))
            if runs and self.state(cid) != "configured" and self.compat(cid, gpu)[0]:
                return {"id": cid, "label": loc(c["label"]), "disk_gb": c["disk_gb"], "minutes": c["minutes"],
                        "state": self.state(cid)}
        return None

    def install(self, cid, gpu):
        if cid not in self.entries:
            raise LaunchError(tr("eng.unknown"))
        ok, why = self.compat(cid, gpu)
        if not ok:
            raise LaunchError(why)
        if names := self.missing(cid):
            raise LaunchError(tr("eng.missing", names=", ".join(names)))
        c = self.entries[cid]

        def work(job):
            env = {"INSTALL_DIR": expand(c["dir"]), "MODELS_DIR": str(self.models_dir()), "GPU_CC": str(gpu and gpu.get("cc") or "")}
            code = job.run(["bash", str(self.dir / c["script"])], env=env, cwd=self.dir)
            if code:
                raise LaunchError(tr("eng.failed", code=code))
            try:
                added = self.registry.add_engine(cid, c["engine"])
            except Exception as e:
                raise LaunchError(tr("eng.not_registered", err=e))
            return tr("eng.registered") if added else tr("eng.kept", id=cid)
        self.jobs.start(cid, self.log_dir / f"engine-{cid}.log", work, busy_msg=tr("eng.running"),
                        msg=tr("eng.installing", dir=c["dir"]))

    def status(self, gpu):
        out = []
        for cid, c in self.entries.items():
            e, job = c["engine"], self.jobs.get(cid)
            ok, why = self.compat(cid, gpu)
            names = self.missing(cid)
            out.append({"id": cid, "label": loc(c["label"]), "desc": loc(c["desc"]), "url": c["url"], "docs": c.get("docs"),
                        "dir": c["dir"], "disk_gb": c["disk_gb"], "minutes": c["minutes"],
                        "kinds": e.get("kinds", []), "file_ext": e.get("file_ext", []),
                        "state": self.state(cid), "compatible": ok, "why": why,
                        "missing": names, "fix": fix_commands([self.reqs[n] for n in names]),
                        "job": job and job.view(log_lines=40)})
        return out
