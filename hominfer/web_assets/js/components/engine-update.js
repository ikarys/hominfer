// Engine update from its git clone (Settings): check, pull + build, the job state with its log.
import { api } from "../api.js";
import { esc } from "../dom.js";
import { t } from "../i18n.js";

export function updateHtml(eid, e) {
  if (!e.repo) return "";
  const checked = e.update?.checked;
  const job = e.update?.job;
  const checkedHtml = checked
    ? (checked.behind.length
      ? `<span><b class="txt-warn">${esc(t("ui.upd.behind", { n: checked.behind.length }))}</b> ${esc(t("ui.upd.behind_on", { branch: checked.branch, current: checked.current }))}</span><pre class="log">${esc(checked.behind.join("\n"))}</pre><button type="button" data-upgrade>${esc(t("ui.upd.upgrade"))}</button>`
      : `<span class="meta">${esc(t("ui.upd.up_to_date", { current: checked.current, branch: checked.branch }))}</span>`)
    : "";
  const jobHtml = job
    ? `<b class="${{ running: "txt-warn", done: "txt-ok", error: "txt-bad" }[job.state]}">${esc(job.msg)}</b>`
      + (job.log ? `<pre class="log">${esc(job.log)}</pre>` : "")
    : "";
  return `<div class="eng-upd" data-upd="${esc(eid)}" data-label="${esc(e.label)}">
    <button type="button" data-check${job?.state === "running" ? " disabled" : ""}>${esc(t("ui.card.check_update"))}</button>
    ${checkedHtml}
    ${jobHtml}</div>`;
}

export function bindEngineUpdates(box, reload, msg) {
  box.addEventListener("click", async e => {
    const btn = e.target.closest("[data-check], [data-upgrade]");
    if (!btn) return;
    const el = btn.closest("[data-upd]");
    if (!el) return;
    const eid = el.dataset.upd, label = el.dataset.label;
    if (btn.hasAttribute("data-check")) {
      btn.disabled = true;
      msg.textContent = "";
      try {
        await api(`/api/engines/${encodeURIComponent(eid)}/check`, {});
        await reload();
      } catch (err) {
        msg.textContent = err.message;
        btn.disabled = false;
      }
    } else {
      if (!confirm(t("ui.upd.confirm", { engine: label }))) return;
      msg.textContent = "";
      try {
        await api(`/api/engines/${encodeURIComponent(eid)}/update`, {});
        const tick = async () => {
          const conf = await reload();
          if (conf?.[eid]?.update.job?.state === "running") setTimeout(tick, 2000);
        };
        tick();
      } catch (err) {
        msg.textContent = err.message;
      }
    }
  });
}
