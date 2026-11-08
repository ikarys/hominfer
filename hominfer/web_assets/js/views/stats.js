import { api } from "../api.js";
import { $, esc } from "../dom.js";
import { t } from "../i18n.js";
import { dur, count } from "../format.js";
import { state } from "../state.js";

const DAY = 86400;
let shown = null;  // [data, from, to] of the chart, redrawn when the window resizes

function setMsg(text) {
  $("#statsMsg").textContent = text;
}

function clearAll() {
  $("#statsTotal").innerHTML = "";
  $("#statsChart").innerHTML = "";
  $("#statsModels").innerHTML = "";
  $("#statsEngines").innerHTML = "";
}

function metric(value, label) {
  return `<div class="metric"><b>${esc(value)}</b><span>${esc(label)}</span></div>`;
}

function peakText(s) {
  if (s.limit != null) return `${s.peak == null ? "–" : count(s.peak)} / ${count(s.limit)}`;
  return s.peak == null ? "–" : count(s.peak);
}

function shareText(share) {
  if (!share || !share.length) return "–";
  return share.map(([n, f]) => `${count(n)}: ${Math.round(f * 100)} %`).join(" · ");
}

function busyPct(up, busy) {
  return up > 0 ? `${Math.round((busy / up) * 100)} %` : "–";
}

function renderTiles(total) {
  const tiles = [
    metric(dur(total.up), t("ui.stats.up")),
    metric(dur(total.busy), t("ui.stats.busy")),
    metric(peakText(total), t("ui.stats.peak"))
  ];
  if (total.peak_waiting != null) tiles.push(metric(count(total.peak_waiting), t("ui.stats.queue")));
  tiles.push(metric(shareText(total.share), t("ui.stats.share")));
  $("#statsTotal").innerHTML = tiles.join("");
}

function modelRow([id, s]) {
  const name = state.models[id]?.name || id;
  const engine = state.engines[s.engine]?.label || s.engine;
  return `<tr><td><strong>${esc(name)}</strong> <span class="meta flat">${esc(id)}</span></td><td>${esc(engine)}</td><td class="num">${esc(dur(s.up))}</td><td class="num">${esc(dur(s.busy))}</td><td class="num">${esc(busyPct(s.up, s.busy))}</td><td class="num">${esc(peakText(s))}</td><td class="num">${s.peak_waiting == null ? "–" : esc(count(s.peak_waiting))}</td><td class="num">${esc(shareText(s.share))}</td></tr>`;
}

function engineRow([id, s]) {
  const label = state.engines[id]?.label || id;
  return `<tr><td><strong>${esc(label)}</strong> <span class="meta flat">${esc(id)}</span></td><td class="num">${esc(dur(s.up))}</td><td class="num">${esc(dur(s.busy))}</td><td class="num">${esc(busyPct(s.up, s.busy))}</td><td class="num">${esc(peakText(s))}</td><td class="num">${s.peak_waiting == null ? "–" : esc(count(s.peak_waiting))}</td><td class="num">${esc(shareText(s.share))}</td></tr>`;
}

function renderTable(selector, entries, headers, rowFn) {
  const table = $(selector);
  table.innerHTML = `<thead><tr>${headers.map((h) => `<th>${esc(t(h))}</th>`).join("")}</tr></thead><tbody>${entries.map(rowFn).join("")}</tbody>`;
}

function sorted(obj) {
  return Object.entries(obj).sort((a, b) => b[1].busy - a[1].busy || b[1].up - a[1].up);
}

function renderTables(data) {
  renderTable("#statsModels", sorted(data.models), ["ui.stats.col_model", "ui.stats.col_engine", "ui.stats.col_up", "ui.stats.col_busy", "ui.stats.col_busy_pct", "ui.stats.col_peak", "ui.stats.col_queue", "ui.stats.col_share"], modelRow);
  renderTable("#statsEngines", sorted(data.engines), ["ui.stats.col_engine", "ui.stats.col_up", "ui.stats.col_busy", "ui.stats.col_busy_pct", "ui.stats.col_peak", "ui.stats.col_queue", "ui.stats.col_share"], engineRow);
}

function r1(n) {
  return Math.round(n * 10) / 10;
}

function hourLabel(ts) {
  const d = new Date(ts * 1000);
  const time = `${String(d.getHours()).padStart(2, "0")}:00`;
  if (d.getHours() !== 0) return time;
  return `${d.toLocaleDateString(t("locale"), { day: "numeric", month: "short" })} ${time}`;
}

function dayLabel(ts) {
  return new Date(ts * 1000).toLocaleDateString(t("locale"), { day: "numeric", month: "short" });
}

function localMidnight(ts, offsetDays = 0) {
  const d = new Date(ts * 1000);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + offsetDays);
  return Math.floor(d.getTime() / 1000);
}

function dateMidnight(value, offsetDays = 0) {
  const [y, m, d] = value.split("-").map(Number);
  return localMidnight(Math.floor(new Date(y, m - 1, d).getTime() / 1000), offsetDays);
}

function buildBuckets(data, from, to) {
  const hours = data.hours || [];
  const buckets = [];
  if (to - from <= 2 * DAY) {
    const start = Math.floor(from / 3600) * 3600;
    const end = Math.ceil(to / 3600) * 3600;
    const map = new Map(hours.map((h) => [h[0], h]));
    for (let ts = start; ts < end; ts += 3600) {
      const h = map.get(ts);
      buckets.push({ ts, label: hourLabel(ts), peak: h ? h[1] : null, busy: h ? h[2] : 0, up: h ? h[3] : 0 });
    }
  } else {
    const start = localMidnight(from);
    const toMid = localMidnight(to);
    const end = to > toMid ? toMid + DAY : toMid;
    const map = new Map();
    for (const h of hours) {
      const d = new Date(h[0] * 1000);
      const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
      const cur = map.get(key) || { peak: null, busy: 0, up: 0 };
      if (h[1] != null) cur.peak = Math.max(cur.peak ?? 0, h[1]);
      cur.busy += h[2];
      cur.up += h[3];
      map.set(key, cur);
    }
    const day = new Date(start * 1000);
    while (Math.floor(day.getTime() / 1000) < end) {
      const ts = Math.floor(day.getTime() / 1000);
      const key = `${day.getFullYear()}-${day.getMonth()}-${day.getDate()}`;
      const v = map.get(key);
      buckets.push({ ts, label: dayLabel(ts), peak: v ? v.peak : null, busy: v ? v.busy : 0, up: v ? v.up : 0 });
      day.setDate(day.getDate() + 1);
    }
  }
  return buckets;
}

function gridValues(max) {
  if (max <= 6) return Array.from({ length: max + 1 }, (_, i) => i);
  const step = Math.max(1, Math.ceil(max / 4));
  const values = [];
  for (let v = 0; v <= max; v += step) values.push(v);
  if (values[values.length - 1] !== max) values.push(max);
  return values;
}

function renderChart(data, from, to) {
  shown = [data, from, to];
  const buckets = buildBuckets(data, from, to);
  const el = $("#statsChart");
  if (!buckets.some((b) => b.peak != null)) {
    el.innerHTML = `<p class="meta flat">${esc(t("ui.stats.no_sessions"))}</p>`;
    return;
  }
  const W = Math.max(320, Math.round(el.clientWidth));  // drawn at the real width: text stays its size
  const H = 180;
  const left = 28;
  const bottom = 20;
  const plotW = W - left;
  const top = 8;
  const plotH = H - bottom - top;
  const baseline = H - bottom;
  const max = Math.max(1, ...buckets.map((b) => b.peak ?? 0));
  const y = (v) => r1(baseline - (v / max) * plotH);
  const slot = plotW / buckets.length;
  const barW = Math.max(1, Math.min(32, r1(slot - 2)));
  const parts = [`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${esc(t("ui.stats.chart"))}">`];
  for (const v of gridValues(max)) {
    const yy = y(v);
    parts.push(`<line x1="${left}" y1="${yy}" x2="${W}" y2="${yy}" stroke="var(--line)" stroke-width="1"></line>`);
    parts.push(`<text x="${left - 4}" y="${r1(yy + 3)}" text-anchor="end" font-size="10" fill="var(--muted)">${esc(String(v))}</text>`);
  }
  buckets.forEach((b, i) => {
    const x0 = r1(left + i * slot);
    const barX = r1(left + i * slot + (slot - barW) / 2);
    const barY = y(b.peak ?? 0);
    const barH = r1(baseline - barY);
    const tip = `${b.label}\n${t("ui.stats.tip", { peak: b.peak == null ? "–" : count(b.peak), busy: dur(b.busy), up: dur(b.up) })}`;
    parts.push(`<g><rect x="${x0}" y="0" width="${r1(slot)}" height="${baseline}" fill="transparent"></rect>`);
    if (b.peak != null && barH > 0) parts.push(`<rect class="bar-fill" x="${barX}" y="${barY}" width="${barW}" height="${barH}" rx="2" fill="var(--accent)"></rect>`);
    parts.push(`<title>${esc(tip)}</title></g>`);
  });
  const labelCount = Math.min(6, buckets.length);
  const indices = labelCount === 1 ? [0] : Array.from({ length: labelCount }, (_, k) => Math.round(k * (buckets.length - 1) / (labelCount - 1)));
  for (const i of indices) {
    const x = r1(left + i * slot + slot / 2);
    parts.push(`<text x="${x}" y="${H - 4}" text-anchor="middle" font-size="10" fill="var(--muted)">${esc(buckets[i].label)}</text>`);
  }
  parts.push(`</svg>`);
  el.innerHTML = parts.join("");
}

async function load(from, to) {
  const locale = t("locale");
  const fmt = (ts) => new Date(ts * 1000).toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
  $("#statsSpan").textContent = `${fmt(from)} → ${fmt(to)}`;
  setMsg("");
  try {
    const data = await api(`/api/stats?from=${from}&to=${to}`);
    if (!data.models || Object.keys(data.models).length === 0) {
      setMsg(t("ui.stats.empty"));
      clearAll();
      return;
    }
    renderTiles(data.total);
    renderTables(data);
    renderChart(data, from, to);
  } catch (err) {
    setMsg(err.message);
    clearAll();
  }
}

function wireRange() {
  window.addEventListener("resize", () => shown && renderChart(...shown));
  const range = $("#statsRange");
  const buttons = Array.from(range.querySelectorAll("[data-range]"));
  const form = $("#statsCustom");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const to = Math.floor(Date.now() / 1000);
      const from = to - Number(btn.dataset.range);
      buttons.forEach((b) => b.classList.remove("on"));
      btn.classList.add("on");
      form.elements.from.value = "";
      form.elements.to.value = "";
      load(from, to);
    });
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const fromVal = form.elements.from.value;
    const toVal = form.elements.to.value;
    if (!fromVal || !toVal) {
      setMsg(t("ui.stats.bad_range"));
      return;
    }
    const from = dateMidnight(fromVal);
    const to = dateMidnight(toVal, 1);
    if (from >= to) {
      setMsg(t("ui.stats.bad_range"));
      return;
    }
    buttons.forEach((b) => b.classList.remove("on"));
    load(from, to);
  });
}

export async function loadStats() {
  const range = $("#statsRange");
  if (!range.dataset.wired) {
    range.dataset.wired = "1";
    wireRange();
  }
  const to = Math.floor(Date.now() / 1000);
  const from = to - 7 * DAY;
  const defaultBtn = range.querySelector("[data-range='604800']");
  if (defaultBtn) defaultBtn.classList.add("on");
  await load(from, to);
}
