// Engine settings (Settings view): default values of the params of the configured engines, one tab
// per engine. Only defaults are editable; the command is shown read-only (it lives in engines.json).
import { api } from "../api.js";
import { $, esc } from "../dom.js";
import { t } from "../i18n.js";
import { bindEngineUpdates, updateHtml } from "./engine-update.js";

let current = null;  // engine whose tab is open, kept across re-renders

export function fieldHtml(eid, p) {
  const id = `ep-${eid}-${p.key}`, ph = t("ui.eng.no_default");
  const input = p.values
    ? `<select id="${esc(id)}" name="${esc(p.key)}"><option value=""${p.default ? "" : " selected"}>${esc(ph)}</option>${
      p.values.map(([v, l]) => `<option value="${esc(v)}"${v === p.default ? " selected" : ""}>${esc(l)}</option>`).join("")}</select>`
    : `<input id="${esc(id)}" name="${esc(p.key)}" type="text" maxlength="200" value="${esc(p.default)}" placeholder="${esc(ph)}">`;
  return `<div class="eng-param"><label for="${esc(id)}">${esc(p.label)}${input}</label>
    <button type="button" class="link" data-reset="${esc(p.key)}" aria-label="${esc(t("ui.eng.reset_named", { label: p.label }))}">${esc(t("ui.eng.reset"))}</button></div>`;
}

function tabHtml(eid, e) {
  const on = eid === current;
  return `<button type="button" role="tab" id="engtab-${esc(eid)}" aria-controls="engpanel-${esc(eid)}"
    aria-selected="${on}" tabindex="${on ? 0 : -1}" data-tab="${esc(eid)}">${esc(e.label)}</button>`;
}

function panelHtml(eid, e) {
  const off = e.installed ? "" : `<div><span class="tag">${esc(t("ui.eng.not_installed"))}</span></div>`;
  return `<form class="eng-panel" role="tabpanel" id="engpanel-${esc(eid)}" aria-labelledby="engtab-${esc(eid)}"
    data-eid="${esc(eid)}"${eid === current ? "" : " hidden"}>${off}
    <pre class="eng-cmd">${esc(e.command)}</pre>${updateHtml(eid, e)}<div class="eng-params">${e.params.map(p => fieldHtml(eid, p)).join("")}</div>
    ${e.params.length ? `<div class="row"><button>${esc(t("ui.form.save"))}</button></div>` : ""}</form>`;
}

export async function loadEngineSettings() {
  try {
    const engines = Object.entries((await api("/api/engines")).configured);
    if (!engines.some(([eid]) => eid === current)) current = engines[0]?.[0] ?? null;
    $("#engSettings").innerHTML = engines.length
      ? `<div class="eng-tabs" role="tablist">${engines.map(([eid, e]) => tabHtml(eid, e)).join("")}</div>
         ${engines.map(([eid, e]) => panelHtml(eid, e)).join("")}`
      : "";
    return Object.fromEntries(engines);
  } catch (err) { $("#engSetMsg").textContent = err.message; }
}

function select(eid, focus) {
  current = eid;
  const box = $("#engSettings");
  box.querySelectorAll("[role=tab]").forEach(b => {
    const on = b.dataset.tab === eid;
    b.setAttribute("aria-selected", on);
    b.tabIndex = on ? 0 : -1;
    if (on && focus) b.focus();
  });
  box.querySelectorAll("[role=tabpanel]").forEach(f => { f.hidden = f.dataset.eid !== eid; });
  $("#engSetMsg").textContent = "";
}

async function save(form) {
  const msg = $("#engSetMsg");
  msg.textContent = "";
  const body = Object.fromEntries(new FormData(form));
  try {
    await api(`/api/engines/${encodeURIComponent(form.dataset.eid)}/params`, body);
    await loadEngineSettings();
    msg.textContent = t("ui.eng.saved");
  } catch (err) { msg.textContent = err.message; }
}

export function bindEngineSettings() {
  const box = $("#engSettings");
  box.addEventListener("submit", e => { e.preventDefault(); save(e.target); });
  box.addEventListener("keydown", e => {  // arrow keys move between tabs (WAI-ARIA tabs pattern)
    if (e.target.getAttribute("role") !== "tab" || !["ArrowLeft", "ArrowRight"].includes(e.key)) return;
    const tabs = [...box.querySelectorAll("[role=tab]")];
    const i = tabs.indexOf(e.target) + (e.key === "ArrowRight" ? 1 : -1);
    select(tabs[(i + tabs.length) % tabs.length].dataset.tab, true);
  });
  box.addEventListener("click", e => {
    const tab = e.target.closest("[data-tab]")?.dataset.tab;
    if (tab) return select(tab);
    const key = e.target.closest("[data-reset]")?.dataset.reset;
    if (key) e.target.closest("form").elements[key].value = "";
  });
  bindEngineUpdates(box, loadEngineSettings, $("#engSetMsg"));
}
