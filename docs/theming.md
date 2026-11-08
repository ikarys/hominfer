# Theming

The look (theme) and the page structure (shell) are chosen independently in Settings. Both are plain
files dropped in a folder: no registry, no build step.

## Themes

A theme is `hominfer/web_assets/css/themes/<name>.css`. `<name>` matches `[a-z0-9_-]{1,32}`.
`auto`, `light` and `dark` are built in (`css/tokens.css`); every other `.css` in the folder is discovered.

Rules:

- The server sets `data-theme="<name>"` on `<html>` (nothing for `auto`) and links only the selected file.
- Scope every rule under `[data-theme="<name>"]`.
- Load fonts with `@import` at the top of the file. No global font link exists.
- A theme may override tokens, restyle the component classes below, add decoration (`::before`, `::first-letter`...).
  It must not change ids, `data-*` attributes or markup, and must not depend on a shell.
- Themes load before `base`, `dashboard` and `manage`, so on equal specificity the base rules win:
  use a scoped selector (`[data-theme="x"] .panel`) to override them.

### Tokens

Colours: `--bg --panel --panel-2 --line --text --muted --faint --accent --accent-ink --ok --warn --err --idle
--seg-1 --seg-2 --seg-other`.
Structure: `--font-body`, `--font-display` (h1, h2, big numbers), `--font-mono`, `--radius` (panels, dialogs),
`--radius-sm` (buttons, metrics), `--border-w`, `--shadow-panel`.

### Component classes

Layout: `panel`, `card`, `cards`, `grid`, `row`, `actions`, `table-wrap`, `wide`, `lib`, `lib-head`, `sys`, `metric`,
`bar`, `legend`, `form`, `field`, `folders`, `opts`.
Text: `meta`, `hint`, `msg`, `big`, `mono`, `num`, `link`, `bad`, `txt-ok`, `txt-warn`, `txt-bad`.
Controls: `button`, `button.primary`, `a.btn`, `input`, `select`, `dialog`.
Helpers: `flat`, `push`, `mt-2`, `mt-8`, `mb-4`, `mb-6`, `my-8`.
Dynamic widths and colours (`bar`, `--c`) stay inline because they come from live data.

### Adding a theme from a mockup

1. Copy `css/themes/neo.css` to `css/themes/<name>.css`, rename the scope.
2. Set tokens first, then restyle classes only where tokens are not enough.
3. Add the label `ui.theme.<name>` to every file in `hominfer/locales/` (tests check it).
4. `just test`, then pick it in Settings.

## Shells

A shell is a folder `hominfer/web_assets/shells/<name>/` with `shell.html` and `shell.css`. The default is
`classic`. Discovery is by `shells/*/shell.html`; `shell.css` is linked last.

`shell.html` must contain:

- the placeholder `{{VIEWS}}`, once (the four views: dashboard, models, stats, settings);
- `{{t:key}}` for texts, `{{BUILD}}` and `{{BUILD_DATE}}` for the build string if wanted;
- `<span id="conn">` (connection state, filled by the script);
- one `a[data-view="home"]`, `a[data-view="manage"]`, `a[data-view="stats"]` and `a[data-view="settings"]`
  (navigation, the script marks the current one active; hrefs `/`, `/models`, `/stats`, `/settings`).

Dialogs are added by `index.html`, outside the shell. No inline `style=` anywhere. A shell styles structure
(header, nav, width, columns), a theme styles looks; keep colours as tokens so every theme works with every shell.

### Overriding a view, adding a script

- `shells/<name>/views/<view>.html` (`home`, `manage`, `stats`, `settings`) replaces the shared `views/<view>.html` for that
  shell; a missing file falls back to the shared one. Overrides keep the ids the shared scripts use, or bring their
  own script.
- `shells/<name>/shell.js` (optional ES module, loaded after `main.js` starts) may export `home = { build, poll }`
  (replaces the dashboard cards and polling, which then run on every view) and `settings` (an async function
  called instead of the default Settings wiring). Only `.js` files of a shell are served, never its HTML.
- The `cockpit` shell uses all of this: status band, event log, model list and detail pane with an action bar, and
  its own Settings layout (engine list with filters, parameter defaults pane). Its detail pane reuses the shared
  model card and drives its buttons, so confirmations stay in one place.

### Adding a shell from a mockup

1. Copy `shells/classic` to `shells/<name>`, change the markup and CSS, keep the contract above.
2. Add `ui.shell.<name>` to every locale file.
3. `just test` renders the page with every theme and shell.

## Locale keys

`ui.theme.<name>` for each theme (except the built-in ones, already present) and `ui.shell.<name>` for each shell.
