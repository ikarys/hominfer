import json

from hominfer.domain import wingpu


def test_windows_gpu_aggregation():
    data = {"samples": [{"n": "pid_1_luid_0x0_0x1_phys_0", "v": 100 * 2**20},
                        {"n": "pid_1_luid_0x0_0x2_phys_0", "v": 150 * 2**20},
                        {"n": "pid_2_luid_0x0_0x1_phys_0", "v": 30 * 2**30},
                        {"n": "pid_3_luid_0x0_0x1_phys_0", "v": 50 * 2**20},
                        {"n": "garbage", "v": 2**40},
                        {"n": "pid_4_luid_0x0_0x1_phys_0", "v": 2 * 2**30}],
            "names": {"1": "dwm", "2": "vmwp"}}
    assert wingpu.aggregate(data) == [{"name": "WSL (models)", "bytes": 30 * 2**30},
                                      {"name": "pid 4", "bytes": 2 * 2**30},
                                      {"name": "dwm", "bytes": 250 * 2**20}]
    assert wingpu.aggregate({}) == []
    assert wingpu.aggregate(json.loads('{"samples": [], "names": {}}')) == []
