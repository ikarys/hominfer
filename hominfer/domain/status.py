"""What the model cards show: state, and per-model VRAM.

Per-model VRAM is inferred: under WSL nvidia-smi only tells which PIDs use the GPU (and on
driver 617.x it reports no PIDs at all, so "on the GPU" is inferred from the allocated VRAM).
- the only model on the GPU, PIDs known   -> VRAM used - baseline (display + WSL)    "live" / "estimate"
- the only model on the GPU, no PIDs      -> VRAM delta at load; "cpu" if 0; and the used - baseline delta
                                             ("live" / "estimate") when there is no load measure
- several models on the GPU               -> VRAM delta measured while it loaded     "load"
- not on the GPU                          -> 0                                       "cpu"
- several, no load measure                -> unknown                                 "shared"
"""


def model_state(*, stopping, running, healthy, failed):
    if stopping:
        return "stopping"
    if not running:
        return "error" if failed else "stopped"
    return "ready" if healthy else "starting"


def model_vram(mid, on_gpu, used_mib, baseline_mib, baseline_measured, load_mib, *, pids_known=True):
    """on_gpu: {model id: uses the GPU}; load_mib: VRAM delta measured at load, or None;
    pids_known: nvidia-smi reported the PIDs that use the GPU (not true under WSL, driver 617.x).
    -> (VRAM in MiB or None, how)."""
    if not on_gpu[mid]:
        return 0, "cpu"
    if [m for m, v in on_gpu.items() if v] == [mid]:
        if not pids_known:  # the live delta would measure the baseline, not the model
            if load_mib == 0:
                return 0, "cpu"
            if load_mib is not None:
                return load_mib, "load"
        return max(0, used_mib - baseline_mib), "live" if baseline_measured else "estimate"
    if load_mib is not None:
        return load_mib, "load"
    return None, "shared"


def on_gpu_for(procs, pids, allocated):
    """procs: {model id: processes}; pids: the PIDs nvidia-smi reports as using the GPU;
    allocated: VRAM is allocated beyond the idle baseline. -> {model id: uses the GPU}.

    Under WSL the PIDs can be empty while a model uses the GPU (driver 617.x): attribute the
    GPU to the running models when VRAM is allocated (a loaded model keeps it, even at util 0)."""
    out = {mid: any(p.pid in pids for p in ps) for mid, ps in procs.items()}
    if not pids and allocated:
        for mid, ps in procs.items():
            if ps:
                out[mid] = True
    return out


def baseline_ok(pids, running, util):
    """Re-measure the idle VRAM baseline (display + WSL) only when the machine is truly idle:
    no compute PID reported, no model process running, GPU at display noise. Otherwise the
    measure would absorb a model's VRAM (a driver releasing it slowly, a Windows app...)."""
    return not pids and not running and (util or 0) < 5
