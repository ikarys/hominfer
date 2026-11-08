// Entry point: one page, three views (/: dashboard, /models: models, /settings: settings)
import { api } from "./api.js";
import { bindEngineCatalog, loadEngines } from "./components/engine-catalog.js";
import { bindFolderPicker } from "./components/folder-picker.js";
import { bindHfBrowser } from "./components/hf-browser.js";
import { bindModelForm } from "./components/model-form.js";
import { on } from "./events.js";
import { settings } from "./i18n.js";
import { state } from "./state.js";
import * as dashboard from "./views/dashboard.js";
import { bindLibrary, loadLibrary } from "./views/library.js";
import { bindModelsTable, renderModelsTable } from "./views/models-table.js";
import { bindEngineSettings, loadEngineSettings } from "./components/engine-settings.js";
import { bindSettings } from "./views/settings.js";

const VIEWS = { "/": "home", "/models": "manage", "/modeles": "manage", "/settings": "settings" };
const VIEW = VIEWS[location.pathname] || "home";
const POLL_MS = 2000;

// a shell may bring a script (docs/theming.md): its own home view { build, poll }, manage() and settings() for its Models and Settings views
document.body.classList.add("page-" + VIEW);
const shell = settings.shellScript ? await import(settings.shellScript) : {};
const { build, poll } = shell.home ?? { build: dashboard.buildCards, poll: dashboard.poll };

// models.json or engines.json changed: fetch them again and redraw (show: model to display)
async function reloadModels(show) {
  const r = await api("/api/models");
  Object.assign(state, { models: r.models, engines: r.engines, kinds: r.kinds, taskKind: r.task_kind });
  build(show);
  renderModelsTable();
  await poll();
  if (VIEW === "manage") loadLibrary();  // elsewhere the model form fetches it when opened
}

on("reload", reloadModels);
on("poll", poll);
bindModelForm();
bindModelsTable();
bindEngineCatalog();
bindHfBrowser();
bindLibrary();
if (!shell.settings) { bindSettings(); bindEngineSettings(); }
bindFolderPicker();
document.querySelector(`.nav [data-view="${VIEW}"]`)?.classList.add("on");

await reloadModels();
// a shell with its own home also shows live data (its status band) on every page
if (VIEW === "home" || shell.home) setInterval(() => document.hidden || poll(), POLL_MS);
if (VIEW === "manage" && shell.manage) await shell.manage();
if (VIEW === "settings") {
  if (shell.settings) await shell.settings();
  else { loadEngines(); loadEngineSettings(); }
}
