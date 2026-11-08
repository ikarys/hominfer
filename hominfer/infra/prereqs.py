"""Is a catalog prerequisite present on this machine? (tool in PATH, or library known to pkg-config)"""
import shutil
import subprocess


def present(req):
    if "cmd" in req:
        return shutil.which(req["cmd"]) is not None
    try:
        return subprocess.run(["pkg-config", "--exists", req["pkgconfig"]], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
