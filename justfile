default: run

# Run in the foreground: http://127.0.0.1:8090 (HOMINFER_HOST=0.0.0.0 for the LAN)
run:
    ./run.sh

# Dev mode: same as run (the page has no build step, reload the browser after an edit)
dev: run

# Run the tests (installs the package and pytest in venv-hominfer first)
test:
    [ -x venv-hominfer/bin/python ] || uv venv -q --python 3.12 venv-hominfer
    uv pip install -q --python venv-hominfer/bin/python -e ".[dev]"
    venv-hominfer/bin/python -m pytest -q

# Start the launcher at boot from this checkout (systemd service, reachable from the LAN)
install-service:
    sudo rm -f /etc/systemd/system/hominfer.service  # old install = symlink to the template
    sed "s|@USER@|$USER|; s|@DIR@|$PWD|" hominfer.service | sudo tee /etc/systemd/system/hominfer.service >/dev/null
    sudo systemctl daemon-reload
    sudo systemctl disable --now ia-launcher 2>/dev/null || true  # pre-rename unit
    sudo systemctl enable --now hominfer

logs-service:
    journalctl -u hominfer -f

start:
    sudo systemctl start hominfer

stop:
    sudo systemctl stop hominfer

# After a code change (also stops the models it started)
restart:
    sudo systemctl restart hominfer
