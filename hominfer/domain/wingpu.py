"""Windows GPU memory per process (WSL: nvidia-smi only sees the VM, Windows processes and the VM
itself all reserve dedicated GPU memory on the same card)."""
import re

from ..i18n import tr

MIN_BYTES = 200 * 2**20
TOP = 6
WSL_PROCESS = "vmwp"  # the VM hosting WSL
_PID = re.compile(r"pid_(\d+)_")


def aggregate(data):
    """data: {"samples": [{"n": counter instance, "v": bytes}], "names": {pid: process name}} as printed by
    the PowerShell query -> [{"name", "bytes"}], biggest first, only processes above MIN_BYTES."""
    per_pid = {}
    for s in data.get("samples", []):
        m = _PID.match(str(s.get("n")))
        if m:
            per_pid[m[1]] = per_pid.get(m[1], 0) + int(s.get("v", 0))
    names = data.get("names", {})
    by_name = {}  # several processes of one program (browser...) count together
    for pid, b in per_pid.items():
        name = names.get(pid) or f"pid {pid}"
        by_name[name] = by_name.get(name, 0) + b
    big = sorted(((n, b) for n, b in by_name.items() if b >= MIN_BYTES), key=lambda x: -x[1])[:TOP]
    return [{"name": tr("ui.sys.wsl_models") if n == WSL_PROCESS else n, "bytes": b} for n, b in big]
