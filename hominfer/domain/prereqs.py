"""Commands that install missing prerequisites (pure)."""


def fix_commands(missing):
    """missing: requirement dicts ("apt" package and / or "install" command) -> shell lines to run."""
    apt = list(dict.fromkeys(r["apt"] for r in missing if "apt" in r))
    return ([f"sudo apt install -y {' '.join(apt)}"] if apt else []) + [r["install"] for r in missing if "install" in r]
