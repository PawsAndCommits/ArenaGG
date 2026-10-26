import { estaAutenticado, esAdmin } from "./auth.js";
import { actualizarActivo, cerrarMenu, toast } from "./layout.js";
import { cargando, errorPagina } from "./components.js";
import { escapar, mensajeError } from "./utils.js";

import * as Inicio from "./pages/inicio.js";
import * as Torneos from "./pages/torneos.js";
import * as Torneo from "./pages/torneo.js";
import * as Sala from "./pages/sala.js";
import * as Login from "./pages/login.js";
import * as Registro from "./pages/registro.js";
import * as Perfil from "./pages/perfil.js";
import * as Equipos from "./pages/equipos.js";
import * as Equipo from "./pages/equipo.js";
import * as EquipoForm from "./pages/equipo-form.js";
import * as Invitaciones from "./pages/invitaciones.js";
import * as Notificaciones from "./pages/notificaciones.js";
import * as Admin from "./pages/admin.js";
import * as TorneoForm from "./pages/torneo-form.js";
import * as MisTorneos from "./pages/mis-torneos.js";
import * as NoEncontrado from "./pages/no-encontrado.js";

const RUTAS = [
  { patron: "/", pagina: Inicio, titulo: "Inicio" },
  { patron: "/torneos", pagina: Torneos, titulo: "Torneos" },
  {
    patron: "/torneos/:id/partidas/:partidaId",
    pagina: Sala,
    titulo: "Sala de partida",
    auth: true,
  },
  { patron: "/torneos/nuevo", pagina: TorneoForm, titulo: "Nuevo torneo", auth: true },
  {
    patron: "/torneos/:id/editar",
    pagina: TorneoForm,
    titulo: "Editar torneo",
    auth: true,
  },
  { patron: "/torneos/:id", pagina: Torneo, titulo: "Torneo" },
  { patron: "/mis-torneos", pagina: MisTorneos, titulo: "Mis torneos", auth: true },
  { patron: "/login", pagina: Login, titulo: "Iniciar sesión", soloInvitado: true },
  { patron: "/registro", pagina: Registro, titulo: "Crear cuenta", soloInvitado: true },
  { patron: "/perfil", pagina: Perfil, titulo: "Mi perfil", auth: true },
  { patron: "/usuarios/:id", pagina: Perfil, titulo: "Perfil" },
  { patron: "/equipos", pagina: Equipos, titulo: "Equipos" },
  { patron: "/equipos/nuevo", pagina: EquipoForm, titulo: "Crear equipo", auth: true },
  { patron: "/equipos/invitaciones", pagina: Invitaciones, titulo: "Invitaciones", auth: true },
  { patron: "/equipos/:id/editar", pagina: EquipoForm, titulo: "Editar equipo", auth: true },
  { patron: "/equipos/:id", pagina: Equipo, titulo: "Equipo" },
  { patron: "/notificaciones", pagina: Notificaciones, titulo: "Notificaciones", auth: true },
  { patron: "/admin", pagina: Admin, titulo: "Administración", auth: true, admin: true },
];

let limpiarActual = null;
let navegacion = 0;

function normalizar(hash) {
  let ruta = (hash || "#/").replace(/^#/, "");
  if (!ruta.startsWith("/")) ruta = `/${ruta}`;
  const [camino, cadena = ""] = ruta.split("?");
  const limpio = camino.length > 1 ? camino.replace(/\/+$/, "") : camino;
  return { ruta: limpio || "/", query: new URLSearchParams(cadena) };
}

function coincidir(patron, ruta) {
  const partesPatron = patron.split("/").filter(Boolean);
  const partesRuta = ruta.split("/").filter(Boolean);
  if (partesPatron.length !== partesRuta.length) return null;
  const params = {};
  for (let indice = 0; indice < partesPatron.length; indice += 1) {
    const parte = partesPatron[indice];
    if (parte.startsWith(":")) {
      params[parte.slice(1)] = decodeURIComponent(partesRuta[indice]);
    } else if (parte !== partesRuta[indice]) {
      return null;
    }
  }
  return params;
}

function buscarRuta(ruta) {
  for (const definicion of RUTAS) {
    const params = coincidir(definicion.patron, ruta);
    if (params) return { ...definicion, params };
  }
  return null;
}

function rutaConQuery(ruta, query) {
  const cadena = query?.toString();
  return `${ruta}${cadena ? `?${cadena}` : ""}`;
}

export function navegar(ruta, { reemplazar = false } = {}) {
  const destino = ruta.startsWith("#") ? ruta : `#${ruta}`;
  if (window.location.hash === destino) {
    cargar();
    return;
  }
  if (reemplazar) {
    window.history.replaceState(null, "", destino);
    cargar();
  } else {
    window.location.hash = destino;
  }
}

export function rutaActual() {
  return normalizar(window.location.hash);
}

function redirigirLogin(ruta, query) {
  const destino = rutaConQuery(ruta, query);
  navegar(`/login?redirect=${encodeURIComponent(destino)}`, { reemplazar: true });
}

function mostrarError(contenedor, error) {
  if (error.status === 404) {
    contenedor.innerHTML = errorPagina("404", "No encontramos lo que buscabas.");
  } else if (error.status === 403) {
    contenedor.innerHTML = errorPagina("403", error.detalle || "No tenés permisos para esta acción.");
  } else {
    contenedor.innerHTML = `
      <div class="error-pagina text-center">
        <div class="error-codigo text-gradiente">${error.status === 0 ? "OFF" : "ERROR"}</div>
        <p class="text-secundario">${escapar(mensajeError(error))}</p>
        <div class="d-flex justify-content-center gap-2">
          <button class="btn btn-rojo" type="button" data-reintentar>
            <i class="bi bi-arrow-clockwise"></i> Reintentar
          </button>
          <a class="btn btn-fantasma" href="#/">Ir al inicio</a>
        </div>
      </div>`;
    contenedor.querySelector("[data-reintentar]")?.addEventListener("click", cargar);
  }
}

async function cargar() {
  const app = document.getElementById("app");
  if (!app) return;

  navegacion += 1;
  const turno = navegacion;
  if (typeof limpiarActual === "function") {
    try {
      limpiarActual();
    } catch (_error) {
      // La página anterior ya no está montada.
    }
    limpiarActual = null;
  }

  const { ruta, query } = normalizar(window.location.hash);
  const definicion = buscarRuta(ruta);
  const contenedor = document.createElement("div");
  contenedor.innerHTML = cargando("Cargando ArenaGG…");
  app.replaceChildren(contenedor);

  if (!definicion) {
    document.title = "No encontrado · ArenaGG";
    NoEncontrado.render(contenedor, { params: {}, query, ruta });
    actualizarActivo(ruta);
    cerrarMenu();
    return;
  }

  if (definicion.soloInvitado && estaAutenticado()) {
    navegar("/", { reemplazar: true });
    return;
  }
  if (definicion.auth && !estaAutenticado()) {
    redirigirLogin(ruta, query);
    return;
  }
  if (definicion.admin && !esAdmin()) {
    toast("Esta sección es solo para administradores.", { titulo: "Acceso restringido", tipo: "disputa" });
    navegar("/", { reemplazar: true });
    return;
  }

  document.title = `${definicion.titulo} · ArenaGG`;
  actualizarActivo(ruta);
  cerrarMenu();
  window.scrollTo({ top: 0, behavior: "instant" });

  try {
    const resultado = await definicion.pagina.render(contenedor, {
      params: definicion.params,
      query,
      ruta,
    });
    if (turno !== navegacion) return;
    if (typeof resultado === "function") limpiarActual = resultado;
  } catch (error) {
    if (turno !== navegacion) return;
    if (error.status === 401) {
      redirigirLogin(ruta, query);
      return;
    }
    mostrarError(contenedor, error);
  }
}

export function iniciarRouter() {
  window.addEventListener("hashchange", cargar);
  window.addEventListener("arenagg:sesion", (evento) => {
    const { ruta, query } = normalizar(window.location.hash);
    const definicion = buscarRuta(ruta);
    if (!definicion) return;
    if (definicion.auth && !estaAutenticado()) return;
    if (definicion.admin && !esAdmin()) {
      navegar("/", { reemplazar: true });
      return;
    }
    if (evento.detail?.motivo === "login" && definicion.soloInvitado) {
      navegar("/", { reemplazar: true });
      return;
    }
    if (evento.detail?.motivo === "perfil") cargar();
  });
  cargar();
}
