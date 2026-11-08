// Shell "cockpit": entry point. main.js takes `home` (the dashboard), `manage` and `settings` from here.
import { clock } from "../../js/format.js";
import { $ } from "../../js/dom.js";
import { build, poll } from "./home.js";
import { start as manage } from "./manage.js";
import { start as settings } from "./settings.js";

export const home = { build, poll };
export { manage, settings };

const tick = () => { $("#ckClock").textContent = clock(); };
tick();
setInterval(tick, 1000);
