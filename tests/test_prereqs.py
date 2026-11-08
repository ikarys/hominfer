from hominfer.domain.prereqs import fix_commands


def test_fix_commands():
    assert fix_commands([]) == []
    missing = [{"apt": "git"}, {"install": "curl x | sh"}, {"apt": "cmake"}, {"apt": "git"}]
    assert fix_commands(missing) == ["sudo apt install -y git cmake", "curl x | sh"]
    assert fix_commands([{"install": "a"}, {"install": "b"}]) == ["a", "b"]
