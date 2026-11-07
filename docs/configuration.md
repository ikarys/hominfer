# Configuration

The launcher keeps three local JSON files in `~/.config/hominfer` (or `HOMINFER_CONFIG_DIR`); files left next to the code by an older git checkout are copied there on first start. None of them
is versioned, and all three are optional: the launcher starts with no engine, no model and the default
settings.

| File | Written by | Holds |
|---|---|---|
| `engines.json` | the engine catalog, or you | how to run each inference engine |
| `models.json` | the page (Add / Edit a model) | the models: engine, file, port, params, profiles |
| `settings.json` | the Settings page | UI language, theme, models folder |

## `engines.json`

How to run each inference engine. The engine catalog adds a block here when it installs an engine. The
page can pick an engine for a model but never writes a command: anything else is edited by hand.
[`engines.example.json`](../engines.example.json) shows a GGUF server and an engine that fetches its own
weights.

| Key | Meaning |
|---|---|
| `label` | name shown in the page |
| `command` | argv (no shell). `~/` is expanded. A nested list is an optional group, dropped if a placeholder in it is empty |
| `env` | extra environment; a variable that ends up empty is dropped |
| `health`, `endpoint` | HTTP paths: readiness check, API shown on the model card |
| `procs` | process names (basename of argv[0] or argv[1]) used to detect the engine |
| `match_file` | also match the model file in argv (one engine binary serving several models) |
| `kinds` | model kinds it runs (`llm`, `decision`, `tts`…) |
| `file_ext` | weight files it loads (`.gguf`…); empty = the engine fetches its own weights |
| `loads_dir` | the engine loads the model's whole folder (all shards), e.g. vLLM |
| `params` | settings per model: `label`, `default`, `values` (menu), `map` (value sent to the engine) |
| `device_param` | param holding `cpu` / `cuda` / `auto` (auto = GPU if enough free VRAM) |
| `provides_repos` | Hugging Face repositories this engine downloads itself |
| `uses` | where those weights land, relative to the models folder (e.g. `hf/models--org--name`) |
| `metrics` | counters shown on the model card, read from the engine's Prometheus endpoint: `{"path": "/metrics", "show": [item, ...]}` (details below) |
| `install_hint` | shown when the engine is missing |
| `repo`, `build`, `binary` | git clone of the engine: enables the "Check for updates" / "Update" buttons (pull + build) |

Placeholders in `command` and `env`: `{port}` `{file}` `{file_name}` `{file_dir}` `{models_dir}`
`{model_id}`, and every param. An argument or an env variable that ends up empty is dropped, which is
how optional params work.

### Engine metrics

`metrics.show` lists up to 16 items, each with a `label` (text or `{"en": ..., "fr": ...}`) and either
`"value": EXPR` or `"ratio": [EXPR_A, EXPR_B]` (A / B; with `"one_minus": true`, 1 - A / B).
`EXPR` is a metric name with an optional label selector, `name` or `name{k="v",k2="v2"}`: the samples
having at least those labels are summed. An item without a match (or dividing by zero) is left out.
`unit`: `count` (default), `bytes`, `pct` (a ratio shown as a percentage) or `x` (2 decimals and `×`).
The launcher reads the endpoint for ready models only, at most every 5 seconds.

## `models.json`

The models, written by the page. Per model:

| Key | Meaning |
|---|---|
| `name`, `desc` | shown on the card |
| `kind` | section of the dashboard (`llm`, `decision`…); `task` (Hugging Face task) fills it for you |
| `engine` | an id of `engines.json` |
| `file` | model file, for engines that load one |
| `port` | where the engine listens |
| `vram_mib` | optional: VRAM to have free before starting. Estimated from the file size when missing |
| `conflicts` | `{"port": "name"}`: other services that must not be running |
| `params` | per engine param: one value (fixed), a list (a menu on the card, first = default), or `[value, label]` pairs |
| `profiles` | named sets of param values, picked on the card |

## `settings.json`

Set from the Settings page and shared by every browser: `lang`, `theme`, `models_dir` (default
`~/hominfer_models`: downloads land there, and engines that fetch their own weights keep them there).

## Text in several languages

Any text of `engines.json`, `models.json` or the catalog (labels, descriptions) can be a plain string or
one string per language: `{"en": "Parallel sessions", "fr": "Sessions parallèles"}`. The page shows the
UI language, falling back to English.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `HOMINFER_HOST` | `127.0.0.1` | listen address (`0.0.0.0` = reachable from the LAN; the page has no login) |
| `HOMINFER_PORT` | `8090` | listen port |
| `HOMINFER_CONFIG_DIR` | `~/.config/hominfer` | where the three JSON files live |
| `HOMINFER_LOG_DIR` | `~/.local/state/hominfer/logs` | model, download and install logs |
| `HOMINFER_MODELS_DIR` | `~/hominfer_models` | models folder until one is set in Settings |
| `HOMINFER_ALLOWED_HOSTS` | empty | extra host names the page is opened by (comma-separated), e.g. a local DNS name; IP addresses, `localhost` and the machine's name always work, any other name gets a 403 |
| `HF_TOKEN` | | Hugging Face token, for gated or private models |

With the systemd service, set them in an override: `sudo systemctl edit hominfer`, then
`[Service]` / `Environment=HOMINFER_PORT=9000`.
