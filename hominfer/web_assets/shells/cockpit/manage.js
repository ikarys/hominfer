// Cockpit Models: filters and Hugging Face on the left, one list (configured models, then files not yet configured),
// detail of the chosen model or of the browsed repository on the right. The shared scripts keep rendering into the
// same ids (the two tables are hidden): their buttons are pressed from here, so forms and confirmations stay shared.
import { deleteModel, openModelForm } from "../../js/components/model-form.js";
import { $, esc } from "../../js/dom.js";
import { size } from "../../js/format.js";
import { t } from "../../js/i18n.js";
import { state } from "../../js/state.js";

let selected = null, sort = "az", sig = "";
const off = new Set();  // unchecked filters: "engine:<id>", "kind:<kind>", "state:<running|stopped>", "source:<configured|disk>"

const run = id => !!state.last?.models[id]?.pids.length;
const phase = id => state.last?.models[id]?.state ?? "stopped";
const fmt = v => Array.isArray(v) ? v.map(x => Array.isArray(x) ? x[0] : x).join(", ") : String(v);

// the on-disk files the shared flow can add as a model: those with an "add" button in the hidden library table
function diskFiles() {
  const files = new Map((state.lib?.items ?? []).flatMap(it => it.files).filter(f => f.path).map(f => [f.path, f]));
  return [...document.querySelectorAll("#libTable [data-use]")].map(b => ({ path: b.dataset.use, ...files.get(b.dataset.use) }))
    .filter(f => f.name);
}

function modelSize(m) {
  const f = (state.lib?.items ?? []).flatMap(it => it.files).find(x => x.path && m.config.file === state.lib.dir + "/" + x.path);
  return f?.size ?? null;
}

const rows = () => Object.entries(state.models).map(([id, m]) => ({ id, m, name: m.name, size: modelSize(m) }));
const cmp = (a, b) => sort === "size" ? (b.size ?? -1) - (a.size ?? -1) : a.name.localeCompare(b.name) * (sort === "az" ? 1 : -1);

function filterHtml(key, items) {
  return items.map(([v, label, n]) => `<label class="ck-check"><input type="checkbox" data-f="${key}:${esc(v)}"${off.has(`${key}:${v}`) ? "" : " checked"}>
    <span>${esc(label)}</span><span class="meta flat">${n}</span></label>`).join("");
}

const tag = x => `<span class="tag">${esc(x)}</span>`;
const tagsOf = m => [m.engine, state.kinds[m.kind] || m.kind, m.task].filter(Boolean).map(tag).join("");

function modelRow({ id, m, size: sz }) {
  return `<li class="ck-eng${id === selected ? " sel" : ""}" data-id="${esc(id)}" data-can="1">
    <i class="ck-dot ${run(id) ? phase(id) : ""}"></i><b>${esc(m.name)}</b>
    <span class="ck-tags">${tagsOf(m)}</span>
    <span class="meta flat">${sz == null ? "–" : size(sz)}</span><span class="meta flat">:${m.port}</span>
    <button type="button" class="ck-gear" data-sel="${esc(id)}" aria-label="${esc(t("ui.ck.m.select", { name: m.name }))}">⚙</button></li>`;
}

const fileRow = f => `<li class="ck-eng ck-off"><i class="ck-dot"></i><b>${esc(f.name)}</b>
  <span class="ck-tags">${tag(t("ui.ck.m.unconfigured"))}</span><span class="meta flat">${size(f.size)}</span>
  <button type="button" class="primary" data-add="${esc(f.path)}" aria-label="${esc(t("ui.ck.m.add_named", { name: f.name }))}">${esc(t("ui.ck.m.add"))}</button>
  ${[...document.querySelectorAll("#libTable [data-del]")].some(b => b.dataset.del === f.path)
    ? `<button type="button" class="link bad" data-rm="${esc(f.path)}">${esc(t("ui.lib.delete"))}</button>` : ""}</li>`;

// the engine's parameters with the value this model really uses; the ones set on the model are the overrides
function paramsOf(m) {
  return Object.entries(state.engines[m.config.engine]?.params ?? {}).map(([k, p]) => {
    const label = v => p.values?.find(([x]) => x === v)?.[1] ?? v;
    const own = m.config.params?.[k];
    const over = own != null && own !== "" && (Array.isArray(own) || String(own) !== p.default);
    const def = p.default ? label(p.default) : t("ui.ck.s.not_set");
    const shown = !over ? (p.default ? label(p.default) : null)
      : Array.isArray(own) ? t("ui.ck.m.on_card", { values: fmt(own) }) : label(String(own));
    return { label: p.label, over, def, shown };
  });
}

function detailHtml() {
  const m = state.models[selected];
  if (!m) return `<p class="meta">${esc(t("ui.ck.m.pick"))}</p>`;
  const ps = paramsOf(m), n = ps.filter(p => p.over).length, up = run(selected);
  const kv = (k, v) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`;
  return `<div class="ck-name"><i class="ck-dot ${up ? phase(selected) : ""}"></i><b>${esc(m.name)}</b></div>
    <div class="ck-tags">${tagsOf(m)}</div>
    <dl class="ck-kv">
      ${kv(t("ui.col.state"), esc(t("ui.state." + phase(selected))))}
      ${kv(t("ui.col.port"), `${m.port} <code>${esc(m.endpoint)}</code>`)}
      ${kv(t("ui.col.file"), `<code>${esc(m.config.file || "–")}</code>`)}
    </dl>
    <dl class="ck-kv">${ps.map(p => `<div class="${p.over ? "ck-set" : ""}"><dt>${esc(p.label)}</dt><dd>${p.shown == null
      ? `<span class="ck-unset">${esc(t("ui.ck.s.not_set"))}</span>`
      : `<b>${esc(p.shown)}</b>${p.over ? ` <span class="ck-def">${esc(t("ui.ck.default", { value: p.def }))}</span>` : ""}`}</dd></div>`).join("")}</dl>
    <p class="meta ck-count">${esc(t(n ? "ui.ck.m.n_over" : "ui.ck.m.none_over", { n }))}</p>
    <div class="ck-big"><button type="button" data-edit>${esc(t("ui.card.edit"))}</button>
      <button type="button" class="${up ? "danger" : "primary"}" data-power="${up ? "stop" : "start"}"${phase(selected) === "stopping" ? " disabled" : ""}>${
      esc(t(up ? "ui.card.stop" : "ui.card.start"))}</button>
      <button type="button" class="danger" data-del-model>${esc(t("ui.form.delete"))}</button></div>`;
}

function render() {
  const all = rows(), disk = diskFiles();
  if (!state.models[selected]) selected = all.sort(cmp)[0]?.id ?? null;
  const engines = [...new Set(all.map(r => r.m.engine_id))];
  $("#ckSummary").textContent = t("ui.ck.m.summary", { n: all.length + disk.length, c: all.length, u: disk.length });
  const kinds = [...new Set(all.map(r => r.m.kind).filter(Boolean))];
  $("#ckFilterKind").innerHTML = filterHtml("kind", kinds.map(k => [k, state.kinds[k] || k, all.filter(r => r.m.kind === k).length]));
  $("#ckFilterEngine").innerHTML = filterHtml("engine", engines.map(e => [e, state.engines[e]?.label ?? e, all.filter(r => r.m.engine_id === e).length]));
  const live = all.filter(r => run(r.id)).length;
  $("#ckFilterState").innerHTML = filterHtml("state", [["running", t("ui.ck.m.running"), live], ["stopped", t("ui.state.stopped"), all.length - live]]);
  $("#ckFilterSource").innerHTML = filterHtml("source", [["configured", t("ui.ck.m.configured"), all.length], ["disk", t("ui.ck.m.unconfigured"), disk.length]]);
  const shownModels = off.has("source:configured") ? [] : all.filter(r => !off.has("engine:" + r.m.engine_id) && !off.has("kind:" + r.m.kind)
    && !off.has("state:" + (run(r.id) ? "running" : "stopped"))).sort(cmp);
  const shownFiles = off.has("source:disk") ? [] : disk.sort(cmp);
  $("#ckModelList").innerHTML = shownModels.map(modelRow).join("") + shownFiles.map(fileRow).join("")
    || `<li class="meta">${esc(t("ui.ck.m.no_match"))}</li>`;
  $("#ckDetail").innerHTML = detailHtml();
}

// poll-driven redraw only when something visible changed
const signature = () => selected + Object.keys(state.models).map(id => id + phase(id) + run(id)).join();
function tick() {
  if (document.hidden || signature() === sig) return;
  sig = signature();
  render();
}

function showHf() {
  const open = $("#hfFiles").innerHTML !== "";
  $("#ckHfPane").hidden = !open;
  $("#ckDetailPane").hidden = open;
}

const pressCard = (id, act) => document.querySelector(`#card-${id} [data-act=${act}]`)?.click();

export async function start() {
  const redraw = () => { sig = signature(); render(); };
  new MutationObserver(redraw).observe($("#libTable"), { childList: true });  // library reloaded
  new MutationObserver(redraw).observe($("#cfgTable"), { childList: true });  // models.json reloaded
  new MutationObserver(showHf).observe($("#hfFiles"), { childList: true });
  $("#ckHfClose").addEventListener("click", () => { $("#hfFiles").innerHTML = ""; });
  $("#ckSort").addEventListener("change", e => { sort = e.target.value; redraw(); });
  document.querySelector(".ck-set-side").addEventListener("change", e => {
    const f = e.target.dataset.f;
    if (f) { e.target.checked ? off.delete(f) : off.add(f); redraw(); }
  });
  const pick = id => { selected = id; $("#hfFiles").innerHTML = ""; redraw(); };
  $("#ckModelList").addEventListener("click", e => {
    const add = e.target.closest("[data-add]")?.dataset.add, rm = e.target.closest("[data-rm]")?.dataset.rm;
    const press = (attr, v) => [...document.querySelectorAll(`#libTable [${attr}]`)].find(b => b.getAttribute(attr) === v)?.click();
    if (add) return press("data-use", add);
    if (rm) return press("data-del", rm);
    const row = e.target.closest("[data-can]");
    if (row) pick(row.dataset.id);
  });
  $("#ckDetail").addEventListener("click", e => {
    if (e.target.closest("[data-edit]")) openModelForm(selected);
    else if (e.target.closest("[data-power]")) pressCard(selected, e.target.closest("[data-power]").dataset.power);
    else if (e.target.closest("[data-del-model]")) deleteModel(selected).then(err => { $("#cfgMsg").textContent = err ?? ""; });
  });
  setInterval(tick, 2000);
  redraw();
}
