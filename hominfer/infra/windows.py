"""Windows host (WSL interop): keep the machine awake while a model is loaded, and the host's
RAM (the WSL VM only sees its own share)."""
import os
import shutil
import subprocess
import time

# ES_CONTINUOUS | ES_SYSTEM_REQUIRED until stdin closes (the screen may still turn off).
# Re-asserted every minute: Windows can silently drop the request (seen after a sleep/resume).
_NO_SLEEP = r'''Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
$eof = [Console]::OpenStandardInput().ReadAsync((New-Object byte[] 1), 0, 1)
do { [void][W.P]::SetThreadExecutionState([uint32]"0x80000001") } until ($eof.Wait(60000))'''


def _powershell():
    # systemd services have no Windows PATH
    path = os.environ.get("PATH", "") + ":/mnt/c/Windows/System32/WindowsPowerShell/v1.0"
    return shutil.which("powershell.exe", path=path)


# Host RAM in bytes: total physical, visible, and free (Win32_ComputerMemory can be broken, so
# the total comes from Win32_ComputerSystem and the visible memory is the fallback; the * 1024
# needs parentheses inside the -f argument list).
_HOST_RAM = ("$os = Get-CimInstance Win32_OperatingSystem; $cs = Get-CimInstance Win32_ComputerSystem; "
             "'{0} {1} {2}' -f $cs.TotalPhysicalMemory, ($os.TotalVisibleMemorySize * 1024), "
             "($os.FreePhysicalMemory * 1024)")

RAM_TTL_S = 30  # a PowerShell start-up is ~0.5 s and the poll is every 2 s
_ram_cache = {"at": 0.0, "value": None}


def host_memory():
    """-> {"used_mib", "total_mib"} of the Windows host, or None outside WSL / interop broken.
    The last good value is kept (a failing query must not make the RAM panel flicker)."""
    now = time.time()
    if now - _ram_cache["at"] < RAM_TTL_S:
        return _ram_cache["value"]
    ps = _powershell()
    if not ps:
        return _ram_cache["value"]
    try:
        total, visible, free = (int(x) for x in
                                subprocess.run([ps, "-NoProfile", "-NonInteractive", "-Command", _HOST_RAM],
                                               capture_output=True, text=True, errors="replace",
                                               timeout=5).stdout.split())
        total = total or visible
        if total <= 0:
            raise ValueError
        _ram_cache["value"] = {"used_mib": round((total - free) / 2**20), "total_mib": round(total / 2**20)}
    except Exception:
        pass  # keep the last good value (or None)
    _ram_cache["at"] = now  # a failing interop must not be probed on every poll
    return _ram_cache["value"]


class KeepAwake:
    """No-op outside WSL or with interop disabled."""

    def __init__(self):
        self.powershell = _powershell()
        self.proc = None

    def set(self, on):
        if not self.powershell or on == (self.proc is not None and self.proc.poll() is None):
            return
        if on:  # released when the process ends, including when the launcher dies (stdin closes)
            self.proc = subprocess.Popen([self.powershell, "-NoProfile", "-NonInteractive", "-Command", _NO_SLEEP],
                                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            self.proc.stdin.close()  # EOF -> PowerShell exits and Windows may sleep again
            self.proc = None
