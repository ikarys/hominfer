// Texts in the UI language, injected by the server in <script id="boot"> (see hominfer/web/page.py)
const boot = JSON.parse(document.getElementById("boot").textContent);

// settings of the launcher (settings.json), and the choices offered
export const settings = { lang: boot.lang, theme: boot.theme, shell: boot.shell, modelsDir: boot.models_dir,
                          themes: boot.themes, shells: boot.shells, shellScript: boot.shell_js, langs: boot.langs, favorites: boot.favorites };

// t("ui.card.stop_confirm", { name }) -> "Stop Qwen?"; unknown {vars} are kept, unknown keys shown as is
export function t(key, vars = {}) {
  const s = boot.strings[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (m, k) => k in vars ? vars[k] : m);
}
