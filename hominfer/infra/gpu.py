"""GPU state: NVIDIA from nvidia-smi, else AMD from the amdgpu driver's sysfs files.

Under WSL, nvidia-smi doesn't report per-process memory (N/A), only which PIDs use the GPU.
amdgpu gives each process's memory in /proc/<pid>/fdinfo. On an APU (integrated GPU) the GPU
also addresses system RAM (GTT) beyond its small carve-out: that "unified" memory counts as VRAM.
"""
import re
import subprocess
import time
from functools import cache
from pathlib import Path

QUERY = "name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw,compute_cap"
RETRY_S = 30  # no NVIDIA GPU / driver: nvidia-smi fails in ~0.2 s, don't pay it on every poll
_retry_at = 0.0


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _smi(*args):
    return subprocess.run(["nvidia-smi", *args], capture_output=True, text=True, timeout=5).stdout


def query():
    """-> {vendor, name, used, total (MiB), util, temp, power, cc, pids, unified} or None without a usable GPU.
    pids: the PIDs known to use the GPU (NVIDIA); AMD gives per-process memory instead (process_mib)."""
    return _nvidia() or _amd()


def _nvidia():
    global _retry_at
    if time.monotonic() < _retry_at:
        return None
    try:
        line = _smi(f"--query-gpu={QUERY}", "--format=csv,noheader,nounits").strip().splitlines()[0]
        name, used, total, util, temp, power, cc = [x.strip() for x in line.split(",")]
        apps = _smi("--query-compute-apps=pid", "--format=csv,noheader").split()
        return {"vendor": "nvidia", "unified": False, "name": name, "used": int(used), "total": int(total), "util": _num(util),
                "temp": _num(temp), "power": _num(power), "cc": _num(cc),
                "pids": {int(p) for p in apps if p.strip().isdigit()}}
    except Exception:
        # ponytail: a transient failure on a real GPU also hides it for RETRY_S
        _retry_at = time.monotonic() + RETRY_S
        return None


DRM, PROC = Path("/sys/class/drm"), Path("/proc")
FDINFO_SIZE = re.compile(r"^drm-(?:total|resident)-(vram|gtt):\s+(\d+)\s*(\w*)", re.M)
UNITS = {"": 1, "KiB": 2**10, "MiB": 2**20, "GiB": 2**30}


def _read(f, scale=1.0):
    try:
        return int(f.read_text()) / scale
    except (OSError, ValueError):
        return None


@cache
def _amd_card():
    """The amdgpu device with the most VRAM (a discrete card over the integrated one), or None."""
    # ponytail: one GPU only; several AMD GPUs would need a list end to end
    cards = [d for d in DRM.glob("card[0-9]*/device") if (d / "mem_info_vram_total").exists()
             and (d / "driver").resolve().name == "amdgpu"]
    return max(cards, key=lambda d: _read(d / "mem_info_vram_total") or 0, default=None)


@cache
def _amd_name(dev):
    try:  # "Krackan [Radeon 840M / 860M Graphics]" -> "Radeon 840M / 860M Graphics"
        out = subprocess.run(["lspci", "-mm", "-s", dev.resolve().name], capture_output=True, text=True,
                             timeout=5).stdout
        name = re.findall(r'"([^"]*)"', out)[2]
        return "AMD " + (re.search(r"\[(.+)\]", name) or [None, name])[1]
    except Exception:
        return "AMD GPU"


def _amd():
    dev = _amd_card()
    if not dev:
        return None
    mib = lambda f: _read(dev / f, 2**20) or 0  # noqa: E731
    # an APU has a uma/ folder (carve-out settings): the GPU also uses system RAM through the GTT
    unified = (dev / "uma").is_dir()
    used, total = mib("mem_info_vram_used"), mib("mem_info_vram_total")
    if unified:
        used, total = used + mib("mem_info_gtt_used"), total + mib("mem_info_gtt_total")
    hwmon = next(dev.glob("hwmon/hwmon*"), None)
    power = hwmon and (_read(hwmon / "power1_average", 1e6) or _read(hwmon / "power1_input", 1e6))
    return {"vendor": "amd", "unified": unified, "name": _amd_name(dev), "used": round(used), "total": round(total),
            "util": _read(dev / "gpu_busy_percent"), "temp": hwmon and _read(hwmon / "temp1_input", 1000),
            "power": power, "cc": None, "pids": set(), "pdev": dev.resolve().name}


def process_mib(pids, pdev, unified):
    """{pid: GPU memory in MiB} from the amdgpu fdinfo of these processes (VRAM, + GTT on an APU).
    Several fds of one process can share a DRM client: each client counts once."""
    out = {}
    for pid in pids:
        clients = {}
        for f in (PROC / str(pid) / "fdinfo").glob("*"):
            try:
                txt = f.read_text()
            except OSError:
                continue
            if "drm-driver:\tamdgpu" not in txt or f"drm-pdev:\t{pdev}" not in txt:
                continue
            cid = re.search(r"drm-client-id:\s+(\d+)", txt)
            sizes = {}
            for kind, n, unit in FDINFO_SIZE.findall(txt):
                sizes[kind] = max(sizes.get(kind, 0), int(n) * UNITS.get(unit, 1))
            clients[cid and cid[1]] = sizes.get("vram", 0) + (sizes.get("gtt", 0) if unified else 0)
        out[pid] = round(sum(clients.values()) / 2**20)
    return out
