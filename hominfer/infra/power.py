"""Keep the machine awake while a model is loaded: Windows host via WSL interop, else systemd-logind."""
import os
import shutil
import subprocess

# ES_CONTINUOUS | ES_SYSTEM_REQUIRED until stdin closes (the screen may still turn off).
# Re-asserted every minute: Windows can silently drop the request (seen after a sleep/resume).
_NO_SLEEP = r'''Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
$eof = [Console]::OpenStandardInput().ReadAsync((New-Object byte[] 1), 0, 1)
do { [void][W.P]::SetThreadExecutionState([uint32]"0x80000001") } until ($eof.Wait(60000))'''


def _powershell():
    # systemd services have no Windows PATH
    path = os.environ.get("PATH", "") + ":/mnt/c/Windows/System32/WindowsPowerShell/v1.0"
    return shutil.which("powershell.exe", path=path)


def _command():
    """Under WSL only Windows decides on sleep (an inhibitor inside the VM is ignored)."""
    if ps := _powershell():
        return [ps, "-NoProfile", "-NonInteractive", "-Command", _NO_SLEEP]
    if inhibit := shutil.which("systemd-inhibit"):  # native Linux: held until cat sees EOF
        return [inhibit, "--what=sleep:idle", "--who=hominfer", "--why=model loaded", "cat"]
    return None


class KeepAwake:
    """No-op without WSL interop nor systemd-inhibit."""

    def __init__(self):
        self.argv = _command()
        self.proc = None

    def set(self, on):
        if not self.argv or on == (self.proc is not None and self.proc.poll() is None):
            return
        if on:  # released when the process ends, including when the launcher dies (stdin closes)
            # ponytail: a refused inhibitor (polkit) exits at once and is retried on the next set(True)
            self.proc = subprocess.Popen(self.argv, stdin=subprocess.PIPE,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            self.proc.stdin.close()  # EOF -> PowerShell exits and Windows may sleep again
            self.proc = None
