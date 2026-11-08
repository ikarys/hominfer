// Cockpit Settings: general settings (shared script), an engine list with filters, the parameters of the chosen engine.
// Same API and install flow as the classic view; only the defaults of the params are editable (the command is read-only).
import { api } from "../../js/api.js";
import { fieldHtml } from "../../js/components/engine-settings.js";
import { bindEngineUpdates, updateHtml } from "../../js/components/engine-update.js";
import { installEngine, loadEngines } from "../../js/components/engine-catalog.js";
import { $, esc } from "../../js/dom.js";
import { on } from "../../js/events.js";
import { t } from "../../js/i18n.js";
import { state } from "../../js/state.js";
import { bindSettings } from "../../js/views/settings.js";

let rows = [], selected = null, editing = false;
const off = new Set();  // unchecked filters: "status:installed", "status:available", "type:<tag>"
let sort = "az";

// the engines to show: the catalog plus the engines already in engines.json (id = same id in both)
function collect(data) {
  const byId = new Map(data.catalog.map(c => [c.id, { id: c.id, label: c.label, cat: c,
    tags: [...c.file_ext, ...c.kinds.map(k => state.kinds[k] || k)] }]));
  for (const [id, e] of Object.entries(data.configured)) {
    const r = byId.get(id) ?? { id, label: e.label, tags: state.engines[id]?.file_ext ?? [] };
    byId.set(id, { ...r, label: e.label, conf: e });
  }
  return [...byId.values()];
}

const visible = r => !off.has("status:" + (r.conf ? "installed" : "available"))
  && (!r.tags.length || r.tags.some(x => !off.has("type:" + x)));

function filterHtml(key, items) {
  return items.map(([v, label, n]) => `<label class="ck-check"><input type="checkbox" data-f="${key}:${esc(v)}"${off.has(`${key}:${v}`) ? "" : " checked"}>
    <span>${esc(label)}</span><span class="meta flat">${n}</span></label>`).join("");
}

function actionHtml(r) {
  if (r.conf) return `<button type="button" class="ck-gear" data-sel="${esc(r.id)}" aria-label="${esc(t("ui.ck.s.gear", { label: r.label }))}">⚙</button>`;
  const c = r.cat;
  if (!c.compatible) return `<span class="meta flat">${esc(c.why)}</span>`;
  if (c.job?.state === "running") return `<span class="meta flat">${esc(t("ui.eng.installing"))}</span>`;
  return `<button type="button" class="primary" data-install="${esc(r.id)}">${esc(t("ui.ck.s.install"))}</button>`;
}

function rowHtml(r) {
  const status = r.conf ? "installed" : "available";
  return `<li class="ck-eng${r.id === selected ? " sel" : ""}" data-id="${esc(r.id)}"${r.conf ? ' data-can="1"' : ""}>
    <i class="ck-dot ${r.conf ? "ready" : ""}"></i><b>${esc(r.label)}</b>
    <span class="ck-tags">${r.tags.map(x => `<span class="tag">${esc(x)}</span>`).join("")}
      <span class="tag ck-status-${status}">${esc(t(r.conf ? "ui.eng.state.configured" : "ui.ck.s.available"))}</span></span>
    ${actionHtml(r)}</li>`;
}

// installed engines first, then by name in the chosen order
const shown = () => rows.filter(visible).sort((a, b) =>
  !a.conf - !b.conf || a.label.localeCompare(b.label) * (sort === "az" ? 1 : -1));

function valueOf(p) {
  if (!p.default) return `<span class="ck-unset">${esc(t("ui.ck.s.not_set"))}</span>`;
  return `<b>${esc(p.values?.find(([v]) => v === p.default)?.[1] ?? p.default)}</b>`;
}

function paramsHtml() {
  const r = rows.find(x => x.id === selected && x.conf);
  if (!r) return `<p class="meta">${esc(t("ui.ck.s.pick"))}</p>`;
  const set = r.conf.params.filter(p => p.default).length;
  const head = `<div class="ck-name"><i class="ck-dot ready"></i><b>${esc(r.label)}</b></div>
    <div class="ck-tags">${r.tags.map(x => `<span class="tag">${esc(x)}</span>`).join("")}</div>`;
  if (editing) return `${head}<form id="ckParamForm" data-eid="${esc(r.id)}"><div class="eng-params">${
    r.conf.params.map(p => fieldHtml(r.id, p)).join("")}</div>
    <div class="ck-big"><button class="primary">${esc(t("ui.form.save"))}</button>
    <button type="button" data-cancel>${esc(t("ui.ck.s.cancel"))}</button></div></form>`;
  return `${head}<dl class="ck-kv">${r.conf.params.map(p =>
    `<div class="${p.default ? "ck-set" : ""}"><dt>${esc(p.label)}</dt><dd>${valueOf(p)}</dd></div>`).join("")}</dl>
    <p class="meta ck-count">${esc(t(set ? "ui.ck.s.n_set" : "ui.ck.s.none_set", { n: set }))}</p>
    <div class="eng-cmd-box"><div class="caption">${esc(t("ui.ck.s.command"))}</div><pre class="eng-cmd">${esc(r.conf.command)}</pre></div>
    ${updateHtml(r.id, r.conf)}
    ${r.conf.params.length ? `<div class="ck-big"><button type="button" class="primary" data-edit>${esc(t("ui.ck.s.edit"))}</button>
    <button type="button" data-reset-all${set ? "" : " disabled"}>${esc(t("ui.ck.s.reset"))}</button></div>` : ""}`;
}

function render() {
  const inst = rows.filter(r => r.conf).length;
  $("#ckSummary").textContent = t("ui.ck.s.summary", { n: rows.length, i: inst, a: rows.length - inst });
  $("#ckFilterStatus").innerHTML = filterHtml("status", [["installed", t("ui.eng.state.configured"), inst],
    ["available", t("ui.ck.s.available"), rows.length - inst]]);
  const tags = [...new Set(rows.flatMap(r => r.tags))].sort();
  $("#ckFilterType").innerHTML = filterHtml("type", tags.map(x => [x, x, rows.filter(r => r.tags.includes(x)).length]));
  const list = shown();
  $("#ckEngList").innerHTML = list.map(rowHtml).join("") || `<li class="meta">${esc(t("ui.ck.s.no_match"))}</li>`;
  $("#ckParams").innerHTML = paramsHtml();
}

async function refresh() {
  try {
    const data = await api("/api/engines");
    rows = collect(data);
    if (!rows.some(r => r.id === selected && r.conf)) selected = shown().find(r => r.conf)?.id ?? null;
    render();
    return data.configured;
  } catch (err) { $("#engMsg").textContent = err.message; }
}

async function saveParams(eid, body, msg) {
  try {
    await api(`/api/engines/${encodeURIComponent(eid)}/params`, body);
    editing = false;
    await refresh();
    $("#engMsg").textContent = msg ?? t("ui.eng.saved");
  } catch (err) { $("#engMsg").textContent = err.message; }
}

export async function start() {
  bindSettings();
  on("engines", refresh);  // the install flow reloads the catalog while a job runs
  $("#ckSort").addEventListener("change", e => { sort = e.target.value; render(); });
  document.querySelector(".ck-set-side").addEventListener("change", e => {
    const f = e.target.dataset.f;
    if (f) { e.target.checked ? off.delete(f) : off.add(f); render(); }
  });
  $("#ckEngList").addEventListener("click", e => {
    const id = e.target.closest("[data-install]")?.dataset.install;
    if (id) return installEngine(id, $("#engMsg"));
    const row = e.target.closest("[data-can]");
    if (row) { selected = row.dataset.id; editing = false; render(); }
  });
  $("#ckParams").addEventListener("click", e => {
    const r = rows.find(x => x.id === selected);
    if (e.target.closest("[data-edit]")) { editing = true; $("#ckParams").innerHTML = paramsHtml(); }
    else if (e.target.closest("[data-cancel]")) { editing = false; $("#ckParams").innerHTML = paramsHtml(); }
    else if (e.target.closest("[data-reset-all]") && confirm(t("ui.ck.s.reset_confirm", { label: r.label }))) {
      saveParams(r.id, Object.fromEntries(r.conf.params.map(p => [p.key, ""])));
    } else {
      const key = e.target.closest("[data-reset]")?.dataset.reset;
      if (key) e.target.closest("form").elements[key].value = "";
    }
  });
  $("#ckParams").addEventListener("submit", e => {
    e.preventDefault();
    saveParams(e.target.dataset.eid, Object.fromEntries(new FormData(e.target)));
  });
  bindEngineUpdates($("#ckParams"), refresh, $("#engMsg"));
  await refresh();
  loadEngines();  // starts the catalog's own polling when an install is running
}
