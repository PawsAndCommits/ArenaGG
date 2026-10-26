import { refrescarSesion } from "./auth.js";
import { iniciarLayout } from "./layout.js";
import { iniciarRouter } from "./router.js";

iniciarLayout();
iniciarRouter();
refrescarSesion().catch(() => {});
