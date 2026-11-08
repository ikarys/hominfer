// The event log: /api/events kept in state.events for the views, and the markup of its lines
import { api } from "../api.js";
import { esc } from "../dom.js";
import { clock } from "../format.js";
import { t } from "../i18n.js";
import { state } from "../state.js";

const KEEP = 300;

// fetch what is new; true when something changed
export async function pollEvents() {
  const r = await api(`/api/events?since=${state.eventsLast}`);
  if (r.last < state.eventsLast) {  // the launcher restarted: its ids start again
    state.events = [];
    state.eventsLast = 0;
    return await pollEvents() || true;
  }
  state.eventsLast = r.last;
  if (r.events.length) state.events = [...state.events, ...r.events].slice(-KEEP);
  return r.events.length > 0;
}

// the newest `max` events (optionally one level), latest first, as list items
export function eventItems(max, level) {
  return state.events.filter(e => !level || e.level === level).slice(-max).reverse().map(e => {
    const lv = t("ui.ev.level." + e.level);
    return `<li class="ev ev-${e.level}"><time>${clock(e.t)}</time>`
      + `<span class="ev-mark" role="img" title="${esc(lv)}" aria-label="${esc(lv)}"></span>`
      + `<span>${esc(t(e.key, e.args))}</span></li>`;
  }).join("");
}
