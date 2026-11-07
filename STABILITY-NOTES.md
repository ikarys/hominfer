# Windows PC (NVIDIA): crash diagnosis — temporary note, delete once done

Goal: stability. Check the hardware before touching any software; one test settles it.

1. Right after a crash: `sudo dmesg -T | grep -iE "xid|nvrm"` (under WSL; on Windows: Event Viewer,
   System log, sources `nvlddmkm` and Kernel-Power 41).
   - Xid 79 ("fallen off the bus") or a hard reboot → power / PCIe.
   - Xid 13 / 31 / 43 → driver or application.
2. Under load: `nvidia-smi -q -d POWER,TEMPERATURE`. It shows averages, not the millisecond
   transients: a clean reading does not clear the PSU.
3. Test: `nvidia-smi -pl 450` (admin). If the crashes stop → transients exceed what the PSU or the
   12VHPWR cable holds. The limit resets on reboot (scheduled task / service to keep it).
4. Check the PSU: wattage, the 12VHPWR connector fully seated, no adapter splitter if avoidable.
