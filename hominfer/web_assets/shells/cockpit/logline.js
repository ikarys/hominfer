// One line of process output -> { time, level, msg }. Generic: optional timestamp, then optional level word.
const TS = /^\s*\[?(?:\d{4}-\d\d-\d\d[ T])?(\d\d:\d\d:\d\d)(?:[.,]\d+)?(?:Z|[+-]\d\d:?\d\d)?\]?\s*/;
const LV = /^\[?(debug|trace|info|notice|warn|warning|error|err|fatal|critical)\]?:?(?=\s|$)\s*/i;
const MAP = { error: "alarm", err: "alarm", fatal: "alarm", critical: "alarm", warn: "warn", warning: "warn", info: "run", notice: "run" };

// `prev` is the level of the previous line: continuations (no timestamp, no level word) inherit it
export function parseLogLine(line, prev = "") {
  const ts = TS.exec(line), rest = ts ? line.slice(ts[0].length) : line, lv = LV.exec(rest);
  if (!ts && !lv) return { time: "", level: prev, msg: line };
  return { time: ts?.[1] ?? "", level: lv ? MAP[lv[1].toLowerCase()] ?? "" : "", msg: lv ? rest.slice(lv[0].length) : rest };
}
