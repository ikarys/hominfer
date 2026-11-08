// Numbers for people, in the UI language: sizes, memory, durations
import { t } from "./i18n.js";

const dec = x => x.replace(".", t("num.decimal"));

export const gb = mib => mib == null ? "–" : `${dec((mib / 1024).toFixed(1))} ${t("unit.gb")}`;

export const size = b => b == null ? "–"
  : b >= 2 ** 30 ? `${dec((b / 2 ** 30).toFixed(1))} ${t("unit.gb")}`
  : b >= 2 ** 20 ? `${Math.round(b / 2 ** 20)} ${t("unit.mb")}`
  : `${Math.max(1, Math.round(b / 1024))} ${t("unit.kb")}`;

export const decimal = (x, digits = 1) => dec(x.toFixed(digits));

export const count = n => (n ?? 0).toLocaleString(t("locale"));

// an engine metric (see engines.json "metrics") with its unit
export const metric = (v, unit) => unit === "bytes" ? size(v) : unit === "pct" ? Math.round(v * 100) + " %"
  : unit === "x" ? decimal(v, 2) + "×" : count(Math.round(v));

export function dur(s) {
  if (s == null) return "–";
  if (s < 60) return s + " s";
  if (s < 3600) return Math.floor(s / 60) + " min";
  return Math.floor(s / 3600) + " h " + String(Math.floor(s % 3600 / 60)).padStart(2, "0");
}

export const initials = n => n.split(/[\s\-_.]+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();

// epoch seconds -> hh:mm:ss, local time
export const clock = (epoch = Date.now() / 1000) => new Date(epoch * 1000).toTimeString().slice(0, 8);
