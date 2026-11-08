// Themes and shells offered in Settings (the server renders the chosen ones into the page)
import { esc } from "./dom.js";
import { settings, t } from "./i18n.js";

const options = (values, selected, prefix) => values.map(v =>
  `<option value="${esc(v)}"${v === selected ? " selected" : ""}>${esc(t(prefix + v))}</option>`).join("");

export const themeOptions = () => options(settings.themes, settings.theme, "ui.theme.");
export const shellOptions = () => options(settings.shells, settings.shell, "ui.shell.");
