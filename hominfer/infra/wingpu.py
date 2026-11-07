"""Windows GPU memory per process, sampled in the background (WSL only, through powershell.exe)."""
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

from ..domain.wingpu import aggregate

INTERVAL_S = 30
TIMEOUT_S = 15
SCRIPT = r"""
$s = (Get-Counter '\GPU Process Memory(*)\Dedicated Usage').CounterSamples | ? { $_.CookedValue -gt 1MB } |
  % { @{n=$_.InstanceName; v=[int64]$_.CookedValue} }
$ids = $s | % { if ($_.n -match 'pid_(\d+)_') { [int]$Matches[1] } } | select -Unique
$names = @{}
Get-Process -Id $ids -ErrorAction SilentlyContinue | % { $names["$($_.Id)"] = $_.ProcessName }
@{samples=@($s); names=$names} | ConvertTo-Json -Depth 4 -Compress
"""


def available():
    try:
        wsl = "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False
    return wsl and shutil.which("powershell.exe") is not None


def sample():
    out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", SCRIPT], capture_output=True, text=True,
                         timeout=TIMEOUT_S, stdin=subprocess.DEVNULL).stdout
    return aggregate(json.loads(out))


class WindowsGpu:
    """processes() -> [{name, bytes}] of the last sample, None when unavailable (not WSL, never succeeded)."""

    def __init__(self, sampler=sample):
        self.sampler, self.last = sampler, None

    def start(self):
        if available():
            threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                self.last = self.sampler()
            except Exception:  # keep the last value
                pass
            time.sleep(INTERVAL_S)

    def processes(self):
        return self.last
