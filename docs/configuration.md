# Configuration

Most settings are changed from the page; the JSON files at the bottom are what the page writes and what
you edit by hand for the rest.

## From the page

### Dashboard

- model card: profile menu and param menus pick the start settings; **Save profile…** / **Delete
  profile** (saved in `models.json`); **Edit** opens the model form; ★ marks the favorite model of a
  section (`settings.json`).

### Models

- **Add a model**, **Library → Add as a model**, ⚙ in the models list: the model form (name,
  identifier, kind, engine, Hugging Face task, description, model file, port, params, advanced
  arguments), **Delete this model** in the form (the file is kept) (`models.json`).
- In a param text field one value = fixed, several separated by commas = a menu on the card (first =
  default).
- **Reload models.json** reads the file again after a manual edit.
- **Download from Hugging Face** downloads into the models folder.

### Settings

- **Language**, **Theme**, **Layout**, **Models folder** (`settings.json`)
- **Inference engines**: **Install**, **Update** (adds or rebuilds an engine, `engines.json`)
- **Engine settings** (cockpit layout: engine ⚙ → **Edit parameters** / **Reset to defaults**): default
  value of each engine param, used when a model does not set it; running models keep their command line,
  the next start uses the new defaults (`engines.json`).

Done by hand only: an engine that isn't in the catalog (its command, health check, metrics…), `vram_mib`,
`conflicts`, labelled menu values, texts in several languages, `restart`. After editing `models.json`,
**Reload models.json** picks it up; a change to `engines.json` needs a restart of the launcher.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `HOMINFER_HOST` | `127.0.0.1` | listen address (`0.0.0.0` = reachable from the LAN; the page has no login) |
| `HOMINFER_PORT` | `8090` | listen port |
| `HOMINFER_CONFIG_DIR` | `~/.config/hominfer` | where the three JSON files live |
| `HOMINFER_LOG_DIR` | `~/.local/state/hominfer/logs` | model, download and install logs (a running model's log is emptied past 50 MiB, the 20 latest download logs are kept) |
| `HOMINFER_STATS_FILE` | `~/.local/state/hominfer/stats.json` | usage history shown on the Stats page: hourly buckets per model (up time, busy time by requests running at once, peaks), saved every minute, kept 90 days |
| `HOMINFER_MODELS_DIR` | `~/hominfer_models` | models folder until one is set in Settings |
| `HOMINFER_ALLOWED_HOSTS` | empty | extra host names the page is opened by (comma-separated), e.g. a local DNS name; IP addresses, `localhost` and the machine's name always work, any other name gets a 403 |
| `HF_TOKEN` | | Hugging Face token, for gated or private models |

With the systemd service, set them in an override: `sudo systemctl edit hominfer`, then
`[Service]` / `Environment=HOMINFER_PORT=9000`.

## Configuration files

The launcher keeps three local JSON files in `~/.config/hominfer` (or `HOMINFER_CONFIG_DIR`); files
left next to the code by an older git checkout are copied there on first start. None of them is
versioned, and all three are optional: the launcher starts with no engine, no model and the default
settings.

| File | Written by | Holds |
|---|---|---|
| `engines.json` | the engine catalog, the engine parameters in Settings, or you | how to run each inference engine |
| `models.json` | the page (model form, profiles), or you | the models: engine, file, port, params, profiles |
| `settings.json` | the page (Settings, favorites) | UI language, theme, layout, models folder, favorites |

### `engines.json`

How to run each inference engine. The engine catalog adds a block here when it installs an engine, and
**Settings → Engine settings** changes the `default` of its params. The page never writes a command:
the other keys are edited by hand.
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
| `restart` | restart the model automatically when its engine dies or stops answering its health check after being ready (3 failed checks in a row; at most 3 times an hour). Default `true`; `false` turns it off |
| `install_hint` | shown when the engine is missing |
| `repo`, `build`, `binary` | git clone of the engine: enables "Check for updates" / "Update" (pull + build) on the engine in Settings |

Placeholders in `command` and `env`: `{port}` `{file}` `{file_name}` `{file_dir}` `{models_dir}`
`{model_id}`, and every param. An argument or an env variable that ends up empty is dropped, which is
how optional params work.

#### Engine metrics

`metrics.show` lists up to 16 items, each with a `label` (text or `{"en": ..., "fr": ...}`) and either
`"value": EXPR` or `"ratio": [EXPR_A, EXPR_B]` (A / B; with `"one_minus": true`, 1 - A / B).
`EXPR` is a metric name with an optional label selector, `name` or `name{k="v",k2="v2"}`: the samples
having at least those labels are summed. An item without a match (or dividing by zero) is left out.
`unit`: `count` (default), `bytes`, `pct` (a ratio shown as a percentage) or `x` (2 decimals and `×`).
`event` (optional): `"preemptions"` marks a counter whose increase is logged in the event log.
The launcher reads the endpoint for ready models only, at most every 5 seconds.

`metrics.sessions` (optional) names the gauges of concurrent requests: `{"running": EXPR, "waiting": EXPR,
"limit": EXPR}` (`waiting` and `limit` optional). From the model's start, the card then shows the peak of
requests running at once (against the limit), the queue peak, and how the busy time splits between 1, 2, 3...
requests running: the data to size the engine's max concurrency. They are sampled with the other metrics
(every 5 seconds at most), so very short requests can be missed.

### `models.json`

The models, written by the model form and the profile buttons of the page. Per model (the key is the
form's **Identifier**):

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
| `extra_args` | list of arguments appended to the engine's command (**Advanced arguments** in the form) |
| `profiles` | named sets of param values, picked on the card |

`vram_mib` and `conflicts` are the only keys the form doesn't edit; it keeps them when it saves.

### `settings.json`

Set from the page and shared by every browser: `lang`, `theme`, `shell` (page layout, default `classic`),
`models_dir` (default `~/hominfer_models`: downloads land there, and engines that fetch their own weights
keep them there), `favorites` (the model ids starred on the dashboard).

### Text in several languages

Any text of `engines.json`, `models.json` or the catalog (labels, descriptions) can be a plain string or
one string per language: `{"en": "Parallel sessions", "fr": "Sessions parallèles"}`. The page shows the
UI language, falling back to English.