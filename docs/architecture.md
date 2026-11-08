# Architecture

Two parts, no build step: a Python server (standard library + `psutil` + `huggingface_hub`) and a page
made of plain HTML, CSS and native ES modules.

## Server: the `hominfer` package

Layers whose dependencies point inwards: `web` → `services` → `domain`, with `infra` for system access.
`domain` imports nothing from the other layers and does no I/O.

| Layer | Role |
|---|---|
| `web/` | HTTP: route table (URL → service call), presenters (JSON for the page), page rendering, static files, server (transport, errors) |
| `services/` | use cases: `supervisor` (start / stop / measure), `registry` (engines.json + models.json), `model_editor`, `library`, `downloads`, `catalog` (engine installs), `updates`, `events` (in-memory log of what happened, served by `GET /api/events?since=<id>`), `hub` (Hugging Face verdicts), `settings`, `folders` (folder picker), `jobs` (background jobs) |
| `domain/` | pure rules: engine command building, model validation, compatibility verdicts, card state and VRAM, `events` (what changed between two status snapshots) |
| `infra/` | system access: GPU (`nvidia-smi`, amdgpu sysfs), processes, network, files, Hugging Face, git, sleep inhibition |

- `app.py` wires the services together (composition root); `__main__.py` starts the server.
- `config.py` holds paths and environment settings; `i18n.py` the translations; `errors.py` the one
  error type shown to the user (`LaunchError`).
- Engines run as child processes. They get `PR_SET_PDEATHSIG`, so they stop with the launcher even when
  it is killed.

## Page: `hominfer/web_assets/`

| Path | Role |
|---|---|
| `index.html` | the head and placeholders; `hominfer/web/page.py` composes the page and renders it in the UI language |
| `shells/<name>/` | page structure (`shell.html` with `{{VIEWS}}`, `shell.css`, optional `views/<view>.html` overrides and `shell.js`), discovered from the folder |
| `views/` | `home`, `manage`, `settings` and `dialogs` partials |
| `css/` | `tokens.css` (colours, fonts, shape), `themes/<name>.css` (discovered), `base`, `dashboard`, `manage` |
| `js/main.js` | entry point: picks the view, wires the components, reloads on events |
| `js/views/` | `dashboard` (system panel + cards), `models-table`, `library`, `settings` |
| `js/components/` | `model-card`, `event-log`, `model-form`, `hf-browser`, `engine-catalog`, `folder-picker`, `sparkline` |
| `js/*.js` | `api`, `state` (what the page knows), `events` (tiny bus), `i18n` (`t()`), `dom`, `format`, `theme` |

## Translations

Every text shown to the user comes from `hominfer/locales/<lang>.json`, with the same keys for the page and the
server: `tr()` in Python, `t()` in JavaScript, `{{t:key}}` in the HTML files. The server renders the page in
the UI language and injects the strings the scripts need.

## Engine catalog

`hominfer/catalog/catalog.json` lists installable engines: description, disk and time estimates, GPU vendors it
builds for (`gpu`), minimum NVIDIA generation (`min_cc`), install folder, and the block added to `engines.json`. Each one has an idempotent
script, `catalog/<engine>.sh`: running it again updates or reconfigures. The scripts share
`hominfer/catalog/lib.sh` (CUDA toolkit from pip wheels, GPU architecture, git checkout) and receive
`INSTALL_DIR`, `MODELS_DIR` and `GPU_CC` in their environment.

The page only sends a catalog id: scripts always come from this repository, never from the page. An engine
id already in `engines.json` is left untouched.

Themes and shells: see [theming.md](theming.md).
