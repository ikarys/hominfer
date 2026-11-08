"""Engine updates from their git clone: pull + build while models keep running.

A running process keeps the old binary (the linker writes a new file). A failed build goes
back to the previous commit and binary.
"""
import os
import shutil
import subprocess
from pathlib import Path

from ..errors import LaunchError
from ..i18n import loc, tr
from ..infra import git
from .jobs import Jobs


class Updates:
    def __init__(self, registry, log_dir, events=None):
        """events: the EventLog that gets the results of checks and updates."""
        self.registry, self.log_dir, self.events = registry, log_dir, events
        self.jobs = Jobs()
        self.checked = {}

    def _log(self, level, key, eid, **args):
        if self.events:
            e = self.registry.engines[eid]
            self.events.add(level, key, None, name=loc(e["label"]), **args)

    def check(self, eid):
        e = self.registry.engines[eid]
        found = git.behind(e["repo"])
        if found["behind"]:
            self._log("warn", "update_behind", eid, n=len(found["behind"]), branch=found["branch"])
        else:
            self._log("info", "update_current", eid, branch=found["branch"])
        self.checked[eid] = found
        return found

    def behind(self, eid):
        return len(self.checked.get(eid, {}).get("behind", []))

    def start(self, eid):
        e = self.registry.engines[eid]
        self.jobs.start(eid, self.log_dir / f"{eid}-update.log", lambda job: self._apply(job, eid, e),
                        busy_msg=tr("upd.running"), msg="git pull…")
        self._log("run", "update_started", eid)

    def _apply(self, job, eid, e):
        try:
            msg = self._pull_and_build(job, e)
        except Exception as err:
            self._log("alarm", "update_failed", eid, detail=str(err))
            raise
        self._log("run", "update_done", eid, detail=msg)
        self.checked.pop(eid, None)
        return msg

    @staticmethod
    def _pull_and_build(job, e):
        repo = Path(e["repo"])
        binary = repo / e["binary"]
        prev = binary.with_name(binary.name + ".prev")
        with open(job.log_path, "w") as log:
            def sh(*cmd):
                log.write(f"\n$ {' '.join(cmd)}\n")
                log.flush()
                return subprocess.run(cmd, cwd=repo, stdin=subprocess.DEVNULL, stdout=log,
                                      stderr=subprocess.STDOUT).returncode == 0

            if git.output(repo, "status", "--porcelain", "--untracked-files=no"):
                raise LaunchError(tr("upd.local_changes"))
            old = git.output(repo, "rev-parse", "--short", "HEAD")
            if not sh("git", "merge", "--ff-only", "@{u}"):
                raise LaunchError(tr("upd.pull_failed"))
            new = git.output(repo, "rev-parse", "--short", "HEAD")
            shutil.copy2(binary, prev)
            job.msg = tr("upd.building", old=old, new=new)
            if not sh("nice", "-n", "19", *e["build"]):
                sh("git", "reset", "--hard", old)
                os.replace(prev, binary)
                raise LaunchError(tr("upd.build_failed", old=old))
            return tr("upd.done", old=old, new=new)

    def status(self, eid):
        job = self.jobs.get(eid)
        return job and job.view(log_lines=20)
