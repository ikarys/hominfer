// Cockpit home: model list (left), detail + action bar (middle), process log and events (right).
// The detail is the shared model card: the bar presses the card's own buttons.
import { api } from "../../js/api.js";
import { eventItems, pollEvents } from "../../js/components/event-log.js";
import { bindCard, cardHtml, updateCard } from "../../js/components/model-card.js";
import { $, esc } from "../../js/dom.js";
import { gb } from "../../js/format.js";
import { t } from "../../js/i18n.js";
import { state } from "../../js/state.js";
import { favFirst, isFav, renderWindowsGpu, saveFav } from "../../js/views/dashboard.js";
import { buildGauges, updateBand } from "./band.js";
import { parseLogLine } from "./logline.js";

const EVENTS_SHOWN = 200, LOG_LINES = 500;
const BAR = { start: "[data-act=start]", stop: "[data-act=stop]" };
let selected = null, picked = false, level = "", logBusy = false, logShown = null;

const card = id => $("#card-" + id);

function rowHtml(id, m) {
  return `<li class="ck-row" data-id="${esc(id)}">
    <button type="button" class="ck-pick" data-pick="${esc(id)}" aria-label="${esc(t("ui.ck.pick", { name: m.name }))}">
      <span class="ck-line"><i class="ck-dot"></i><b>${esc(m.name)}</b><span class="ck-st" data-k="state"></span></span>
      <span class="ck-sub">${esc(m.engine)} · :${esc(m.port)}<span class="ck-vram" data-k="vram"></span></span>
    </button>
    <button type="button" class="ck-fav" data-fav="${esc(id)}" aria-pressed="${isFav(id)}"
      title="${esc(t(isFav(id) ? "ui.card.unfav" : "ui.card.fav"))}" aria-label="${esc(t(isFav(id) ? "ui.card.unfav" : "ui.card.fav"))}">★</button>
  </li>`;
}

// the option menus of the card: mark the ones that differ from the engine default and say what the default is
function decorate(id) {
  const c = card(id), m = state.models[id];
  for (const o of m.options) {
    const shown = o.choices.find(([v]) => v === o.default)?.[1] ?? o.default;
    $(`[data-opt="${o.key}"]`, c).closest("label")
      .insertAdjacentHTML("beforeend", `<small class="ck-def">${esc(t("ui.ck.default", { value: shown }))}</small>`);
  }
  c.addEventListener("change", () => markOverrides(id));
}

function markOverrides(id) {
  const m = state.models[id];
  for (const o of m.options) {
    const sel = $(`[data-opt="${o.key}"]`, card(id));
    sel.classList.toggle("ck-over", sel.value !== o.default);
  }
}

function select(id) {
  selected = id;
  for (const mid of Object.keys(state.models)) card(mid).hidden = mid !== id;
  document.querySelectorAll(".ck-row").forEach(r => r.classList.toggle("sel", r.dataset.id === id));
  document.querySelectorAll(".ck-pick").forEach(b => b.setAttribute("aria-pressed", b.dataset.pick === id));
  syncBar();
  refreshLog();
}

// process output of the selected model; the poll calls it, never two requests at once
async function refreshLog() {
  const id = selected, box = $("#ckProcLog");
  if (!id || logBusy || !state.models[id]) return;
  $("#ckProcTitle").textContent = t("ui.ck.proc_log", { name: state.models[id].name });
  logBusy = true;
  try {
    const { log } = await api(`/api/logs/${id}`);
    if (id !== selected) return;
    const s = state.last?.models[id];
    const key = id + "\0" + log;
    if (key === logShown) return;  // unchanged: keep the DOM and the scroll position
    logShown = key;
    const atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 20;
    let prev = "";
    box.innerHTML = log ? log.split("\n").slice(-LOG_LINES).filter(l => l.trim()).map(l => {
      const p = parseLogLine(l, prev);
      prev = p.level;
      return `<li class="ev${p.level ? " ev-" + p.level : ""}"><time>${esc(p.time)}</time><span class="ev-mark"></span><span>${esc(p.msg)}</span></li>`;
    }).join("")
      : `<li class="meta">${esc(t(s?.managed === false && s?.pids.length ? "ui.card.external_logs" : "ui.card.no_logs"))}</li>`;
    if (atBottom) box.scrollTop = box.scrollHeight;
  } catch { /* the header reports a dead launcher */ }
  finally { logBusy = false; if (id !== selected) refreshLog(); }
}

export function build(show) {
  const ids = favFirst(Object.keys(state.models));  // the first one is shown unless a model runs
  if (show && state.models[show]) { selected = show; picked = true; }
  if (!state.models[selected]) selected = ids[0] ?? null;
  $("#cards").innerHTML = ids.map(id => cardHtml(id, state.models[id], id !== selected)).join("");
  $("#ckModels").innerHTML = ids.length ? ids.map(id => rowHtml(id, state.models[id])).join("")
    : `<li class="meta">${esc(t("ui.ck.empty"))}</li>`;
  ids.forEach(id => { bindCard(id); decorate(id); markOverrides(id); });
  if (selected) select(selected);
}

// the bar mirrors the card's buttons: disabled when the card's is, or when it is missing / hidden
function syncBar() {
  document.querySelectorAll("[data-bar]").forEach(b => {
    const src = selected && $(BAR[b.dataset.bar], card(selected));
    b.disabled = !src || src.disabled || !!src.closest("[hidden]");
  });
}

function renderRow(id, s) {
  const row = $(`.ck-row[data-id="${id}"]`);
  if (!row) return;
  const running = s.pids.length > 0;
  row.className = `ck-row ${s.state}${id === selected ? " sel" : ""}`;
  $("[data-k=state]", row).textContent = t("ui.state." + s.state) + (s.state === "ready" && !s.managed ? t("ui.state.external") : "");
  $("[data-k=vram]", row).textContent = running ? " · " + (s.vram_how === "shared" ? "?" : gb(s.vram_mib)) : "";
}

function render(st) {
  state.last = st;
  if (!picked) {  // first look: show a model that is running
    const live = Object.keys(st.models).find(id => st.models[id].pids.length && card(id));
    if (live) select(live);
    picked = true;
  }
  for (const [id, s] of Object.entries(st.models)) {
    if (!card(id)) continue;  // removed from the config since the last reload
    updateCard(id, s, st);
    markOverrides(id);
    renderRow(id, s);
  }
  if (st.gpu) renderWindowsGpu(st.gpu); else $("#winGpu").hidden = true;
  updateBand(st);
  syncBar();
}

function renderEvents() {
  $("#ckEvents").innerHTML = eventItems(EVENTS_SHOWN, level) || `<li class="meta">${esc(t("ui.events.empty"))}</li>`;
}

// the header only says something when the launcher stops answering
export async function poll() {
  try {
    const [st] = await Promise.all([api("/api/status"), pollEvents()]);
    $("#conn").textContent = "";
    renderEvents();
    if (st.ready) {
      render(st);
      // ponytail: refreshed on every poll tick only while the model runs; a stopped one is fetched on selection
      if (selected && st.models[selected]?.pids.length) refreshLog();
    }
  } catch {
    $("#conn").textContent = t("ui.conn.down");
  }
}

buildGauges();
$("#ckModels").addEventListener("click", e => {
  const pick = e.target.closest("[data-pick]")?.dataset.pick;
  if (pick) { picked = true; select(pick); return; }
  const fav = e.target.closest("[data-fav]")?.dataset.fav;
  if (fav) toggleFav(fav);
});

async function toggleFav(id) {
  try {
    await saveFav(id);
    build(selected);
    if (state.last) render(state.last);
  } catch (err) { $("#conn").textContent = err.message; }
}
$("#ckBar").addEventListener("click", e => {
  const b = e.target.closest("[data-bar]");
  if (b && selected) $(BAR[b.dataset.bar], card(selected))?.click();
});
$("#ckFilters").addEventListener("click", e => {
  const b = e.target.closest("[data-level]");
  if (!b) return;
  level = b.dataset.level;
  document.querySelectorAll("#ckFilters button").forEach(x => x.setAttribute("aria-pressed", x === b));
  renderEvents();
});
