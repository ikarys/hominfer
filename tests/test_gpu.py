from hominfer.infra import gpu


def test_failing_nvidia_smi_is_not_rerun_on_every_poll(monkeypatch):
    calls = []

    def smi(*args):
        calls.append(args)
        raise FileNotFoundError("nvidia-smi")
    monkeypatch.setattr(gpu, "_smi", smi)
    monkeypatch.setattr(gpu, "_retry_at", 0.0)
    assert gpu._nvidia() is None and gpu._nvidia() is None
    assert len(calls) == 1


def fake_amd(tmp_path, monkeypatch, apu):
    dev = tmp_path / "drm" / "card1" / "device"
    (dev / "hwmon" / "hwmon3").mkdir(parents=True)
    (tmp_path / "drv" / "amdgpu").mkdir(parents=True)
    (dev / "driver").symlink_to(tmp_path / "drv" / "amdgpu")
    files = {"mem_info_vram_used": 2 * 2**30, "mem_info_vram_total": 8 * 2**30, "mem_info_gtt_used": 2**30,
             "mem_info_gtt_total": 12 * 2**30, "gpu_busy_percent": 7,
             "hwmon/hwmon3/temp1_input": 41000, "hwmon/hwmon3/power1_average": 4500000}
    for f, v in files.items():
        (dev / f).write_text(f"{v}\n")
    if apu:
        (dev / "uma").mkdir()
    monkeypatch.setattr(gpu, "DRM", tmp_path / "drm")
    monkeypatch.setattr(gpu, "_nvidia", lambda: None)
    monkeypatch.setattr(gpu, "_amd_name", lambda dev: "AMD Radeon")
    gpu._amd_card.cache_clear()
    return dev


def test_amd_apu_counts_the_gtt_as_gpu_memory(tmp_path, monkeypatch):
    fake_amd(tmp_path, monkeypatch, apu=True)
    g = gpu.query()
    gpu._amd_card.cache_clear()
    assert (g["vendor"], g["unified"], g["used"], g["total"]) == ("amd", True, 3072, 20480)
    assert (g["util"], g["temp"], g["power"], g["cc"]) == (7, 41, 4.5, None)


def test_amd_discrete_card_counts_its_vram_only(tmp_path, monkeypatch):
    fake_amd(tmp_path, monkeypatch, apu=False)
    g = gpu.query()
    gpu._amd_card.cache_clear()
    assert (g["unified"], g["used"], g["total"]) == (False, 2048, 8192)


def test_process_mib_from_fdinfo(tmp_path, monkeypatch):
    fd = tmp_path / "42" / "fdinfo"
    fd.mkdir(parents=True)
    info = ("drm-driver:\tamdgpu\ndrm-client-id:\t{cid}\ndrm-pdev:\t0000:c4:00.0\n"
            "drm-total-gtt:\t3 GiB\ndrm-resident-gtt:\t3 GiB\ndrm-total-vram:\t512 MiB\n")
    (fd / "5").write_text(info.format(cid=7))
    (fd / "6").write_text(info.format(cid=7))  # same client through another fd: counted once
    (fd / "7").write_text("pos:\t0\nflags:\t02\n")
    monkeypatch.setattr(gpu, "PROC", tmp_path)
    assert gpu.process_mib([42, 99], "0000:c4:00.0", unified=True) == {42: 3584, 99: 0}
    assert gpu.process_mib([42], "0000:c4:00.0", unified=False) == {42: 512}
