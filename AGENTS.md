# Hominfer

Local launcher for inference engines (llama.cpp, vLLM...): start / stop models, watch VRAM, RAM and
CPU, download from Hugging Face, install engines. Python server (stdlib + `psutil` + `huggingface_hub`)
and a plain HTML / ES modules page, no build step. Runs on Linux and under WSL.

## Layout

- `hominfer/`: server. Layers `web` → `services` → `domain`, system access in `infra`
  (details: [docs/architecture.md](docs/architecture.md)).
- `hominfer/web_assets/`: the page (`index.html`, `css/`, `js/`), shipped in the package.
- `hominfer/locales/`: UI strings, one JSON per language.
- `hominfer/catalog/`: engine install recipes (`catalog.json` + one script each).
- `install.sh`: curl installer (uv tool install, optional systemd service).
- `tests/`: pytest, no GPU and no local config needed.
- `docs/`: architecture, configuration (JSON files, env vars), how-to.

## Commands

- `just test`: create the venv if needed, run pytest.
- `just run`: launcher on http://127.0.0.1:8090 (`HOMINFER_HOST=0.0.0.0` for the LAN).
- Second instance for trials: `HOMINFER_PORT=8091 HOMINFER_CONFIG_DIR=/tmp/hominfer-dev venv-hominfer/bin/python -m hominfer`.

## Rules

- No model or engine name in the code: they live in `engines.json`, `models.json` or the catalog.
- `domain/` does no I/O and imports no other layer; `web/` only maps HTTP to service calls.
- Every user-facing string is a locale key present in every file of `hominfer/locales/` (tests check it).
- No new dependency without a stated reason; the page uses no framework.
- Tests for domain rules and services.

## Style

English for code, comments, docs and commits. Small single-purpose modules.

## Commits

Imperative summary line (no prefix), blank line, prose body explaining why. One topic per commit.
Other contribution details: [CONTRIBUTING.md](CONTRIBUTING.md).
