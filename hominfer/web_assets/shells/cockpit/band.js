// The status band: five arc gauges (home) or compact bars (other pages), global state light, GPU name
import { $, esc } from "../../js/dom.js";
import { decimal, gb } from "../../js/format.js";
import { t } from "../../js/i18n.js";
import { state } from "../../js/state.js";

const R = 24, ARC = Math.PI * R, CX = 32, CY = 34;
const RECENT_S = 600;  // an alarm event counts for ten minutes
const GAUGES = [["vram", "VRAM"], ["ram", "ui.sys.ram"], ["cpu", "CPU"], ["temp", "ui.ck.temp"], ["power", "ui.ck.power"]];
const POWER_MAX_W = 600;  // scale of the power gauge when the card reports no limit

const point = (frac, r) => [CX + r * Math.cos(Math.PI * (1 - frac)), CY - r * Math.sin(Math.PI * (1 - frac))];
const ticks = () => Array.from({ length: 11 }, (_, i) => {
  const [x1, y1] = point(i / 10, R + 3), [x2, y2] = point(i / 10, R + (i % 5 ? 5 : 7));
  return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"/>`;
}).join("");

const label = l => l.startsWith("ui.") ? t(l) : l;

// ok / warn / err from a value and its two thresholds (exceeded, not just reached)
const level = (v, warn, err) => v > err ? "err" : v > warn ? "warn" : "ok";

export function buildGauges() {
  $("#ckGauges").innerHTML = GAUGES.map(([k, l]) => `
    <div class="ck-gauge ok" data-g="${k}">
      <svg viewBox="0 0 64 42" aria-hidden="true"><g class="ck-ticks">${ticks()}</g>
        <path class="ck-track" d="M${CX - R} ${CY} A${R} ${R} 0 0 1 ${CX + R} ${CY}"/>
        <path class="ck-fill" d="M${CX - R} ${CY} A${R} ${R} 0 0 1 ${CX + R} ${CY}" stroke-dasharray="0 ${ARC.toFixed(1)}"/></svg>
      <b data-k="v">–</b><span class="ck-unit" data-k="u"></span><span class="ck-label">${esc(label(l))}</span>
    </div>`).join("");
}

function setGauge(key, frac, value, unit, lvl) {
  const g = $(`[data-g="${key}"]`);
  if (!g) return;
  g.className = "ck-gauge " + lvl;
  $(".ck-fill", g).setAttribute("stroke-dasharray", `${(Math.min(Math.max(frac, 0), 1) * ARC).toFixed(1)} ${ARC.toFixed(1)}`);
  $("[data-k=v]", g).textContent = value;
  $("[data-k=u]", g).textContent = unit;
  g.setAttribute("role", "img");
  g.setAttribute("aria-label", `${label(GAUGES.find(x => x[0] === key)[1])} ${value} ${unit}`);
}

// the global light: alarm = a model crashed recently or a ready model fails its health check;
// warning = Windows reserves more GPU memory than the card has, or VRAM above 90 %
function globalState(st) {
  const g = st.gpu;
  if (Object.values(st.models).some(m => m.state === "error")
    || state.events.some(e => e.level === "alarm" && st.time - e.t < RECENT_S)) return "alarm";
  const win = (g?.processes || []).reduce((n, p) => n + p.bytes, 0) / 2 ** 20;
  return g && (win > g.total || g.used / g.total > 0.9) ? "warn" : "ok";
}

const mini = (name, frac, text, lvl) => `<span class="ck-m ${lvl}"><i>${esc(name)}</i>
  <span class="bar"><span style="width:${Math.min(frac, 1) * 100}%"></span></span><b>${esc(text)}</b></span>`;

export function updateBand(st) {
  const g = st.gpu, ram = st.ram, cpu = Math.round(st.cpu.pct);
  const vram = g ? g.used / g.total : 0, ramFrac = ram.used_mib / ram.total_mib;
  const vramLvl = level(vram * 100, 80, 95), ramLvl = level(ramFrac * 100, 80, 95), cpuLvl = level(cpu, 80, 95);
  const tempLvl = g?.temp != null ? level(g.temp, 79, 94) : "ok";  // warning from 80 °C
  const power = g?.power != null ? g.power / (g.power_max || POWER_MAX_W) : 0, powerLvl = level(power * 100, 85, 98);
  $("#ckGpu").textContent = g ? `${g.name.replace("NVIDIA GeForce ", "").replace(" Graphics", "")} · ${gb(g.total)}` : "";
  setGauge("vram", vram, g ? decimal(g.used / 1024) : "–", g ? "/ " + gb(g.total) : "", vramLvl);
  setGauge("ram", ramFrac, decimal(ram.used_mib / 1024), "/ " + gb(ram.total_mib), ramLvl);
  setGauge("cpu", cpu / 100, String(cpu), "%", cpuLvl);
  setGauge("temp", (g?.temp ?? 0) / 100, g?.temp != null ? String(g.temp) : "–", "°C", tempLvl);
  setGauge("power", power, g?.power != null ? String(Math.round(g.power)) : "–", g?.power != null ? "/ " + Math.round(g.power_max || POWER_MAX_W) + " W" : "W", powerLvl);
  $("#ckMini").innerHTML = (g ? mini("VRAM", vram, `${gb(g.used)} / ${gb(g.total)}`, vramLvl) : "")
    + mini(t("ui.sys.ram"), ramFrac, `${gb(ram.used_mib)} / ${gb(ram.total_mib)}`, ramLvl)
    + `<span class="ck-m ${cpuLvl}"><i>CPU</i><b>${cpu} %</b></span>`
    + (g?.temp != null ? `<span class="ck-m ${tempLvl}"><i>${esc(t("ui.ck.temp"))}</i><b>${g.temp} °C</b></span>` : "")
    + (g?.power != null ? `<span class="ck-m ${powerLvl}"><i>${esc(t("ui.ck.power"))}</i><b>${Math.round(g.power)} W</b></span>` : "");
  const s = globalState(st);
  $("#ckLight").className = "ck-light " + s;
  $("#ckStateText").textContent = t("ui.ck.state." + s);
}
