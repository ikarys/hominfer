#!/usr/bin/env bash
# Installs (or upgrades) Hominfer for the current user with uv.
#   curl -LsSf https://raw.githubusercontent.com/ikarys/hominfer/main/install.sh | bash
#   curl -LsSf https://raw.githubusercontent.com/ikarys/hominfer/main/install.sh | bash -s -- --service --lan
# HOMINFER_SOURCE overrides what gets installed (default: the GitHub main branch).
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install.sh [--service] [--lan] [--port N] [-h|--help]
  --service   Install a systemd system service
  --lan       Listen on 0.0.0.0
  --port N    Port to use (default: 8090)
EOF
}

main() {
  SERVICE=0
  LAN=0
  PORT=8090
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --service) SERVICE=1; shift ;;
      --lan) LAN=1; shift ;;
      --port)
        if [[ $# -lt 2 ]]; then usage; exit 2; fi
        PORT="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) usage; exit 2 ;;
    esac
  done
  if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then usage; exit 2; fi

  if [[ "$(uname -s)" != "Linux" ]]; then
    echo "==> Hominfer installer supports Linux only."
    exit 1
  fi
  if [[ "${EUID}" -eq 0 ]]; then
    echo "==> Run as a normal user, not root."
    exit 1
  fi

  HOST="127.0.0.1"
  if [[ "$LAN" -eq 1 ]]; then
    HOST="0.0.0.0"
  fi

  if ! command -v uv >/dev/null 2>&1; then
    echo "==> Installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi

  echo "==> Installing/upgrading Hominfer"
  uv tool install --upgrade --python 3.12 "${HOMINFER_SOURCE:-git+https://github.com/ikarys/hominfer}"

  BIN="$(command -v hominfer || true)"
  if [[ -z "$BIN" || "$BIN" != /* || ! -x "$BIN" ]]; then
    BIN="$HOME/.local/bin/hominfer"
  fi
  if [[ ! -x "$BIN" ]]; then
    echo "==> Could not find the hominfer binary."
    exit 1
  fi

  if [[ "$SERVICE" -eq 1 ]]; then
    if [[ ! -d /run/systemd/system ]]; then
      echo "==> systemd is not running."
      echo "==> On WSL, add [boot] systemd=true to /etc/wsl.conf, run wsl --shutdown, then rerun with --service."
      echo "==> Meanwhile run: HOMINFER_HOST=$HOST HOMINFER_PORT=$PORT hominfer"
    else
      if ! command -v sudo >/dev/null 2>&1; then
        echo "==> sudo is required for --service."
        exit 1
      fi
      echo "==> Installing systemd service (sudo required)"
      CURRENT_USER="$(id -un)"
      sudo tee /etc/systemd/system/hominfer.service > /dev/null <<EOF
[Unit]
Description=Hominfer
After=network.target

[Service]
User=$CURRENT_USER
Environment=HOMINFER_HOST=$HOST
Environment=HOMINFER_PORT=$PORT
ExecStart="$BIN"
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
      sudo systemctl daemon-reload
      sudo systemctl enable --now hominfer
    fi
  else
    if [[ "$LAN" -eq 1 ]]; then
      echo "==> Run: HOMINFER_HOST=0.0.0.0 HOMINFER_PORT=$PORT hominfer"
    else
      echo "==> Run: HOMINFER_PORT=$PORT hominfer"
    fi
  fi

  echo "==> URL: http://127.0.0.1:$PORT"
  if [[ "$LAN" -eq 1 ]]; then
    IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
    if [[ -n "$IP" ]]; then
      echo "==> LAN URL: http://$IP:$PORT"
    fi
    echo "==> Warning: Hominfer has no authentication; expose it only on a trusted network."
  fi
}

main "$@"
