import { api } from "./api.js";
import { cerrarSesion, esAdmin, estaAutenticado, usuarioActual } from "./auth.js";
import { escapar, fechaRelativa, iconoNotificacion } from "./utils.js";
import { avatar } from "./components.js";

const INTERVALO = 20000;

let resumen = { sin_leer: 0, recientes: [] };
let idsConocidos = null;
let temporizador = null;
let cargandoResumen = false;
let audioListo = false;

function elemento(id) {
  return document.getElementById(id);
}

function zonaUsuario() {
  return elemento("zona-usuario");
}

function renderZonaUsuario() {
  const zona = zonaUsuario();
  if (!zona) return;

  if (!estaAutenticado()) {
    zona.innerHTML = `
      <a class="btn btn-sm btn-fantasma" href="#/login">Iniciar sesión</a>
      <a class="btn btn-sm btn-rojo" href="#/registro">Registrarse</a>`;
    elemento("nav-admin")?.classList.add("d-none");
    elemento("nav-nuevo-torneo")?.classList.add("d-none");
    return;
  }

  const usuario = usuarioActual();
  const contador = resumen.sin_leer || 0;
  zona.innerHTML = `
    <div class="dropdown">
      <button class="btn btn-campana" type="button" data-bs-toggle="dropdown"
              data-bs-auto-close="outside" aria-expanded="false" aria-label="Notificaciones">
        <i class="bi bi-bell"></i>
        <span class="campana-contador ${contador ? "" : "d-none"}" data-contador>${contador}</span>
      </button>
      <div class="dropdown-menu dropdown-menu-end panel-notificaciones">
        <div class="d-flex justify-content-between align-items-center px-3 py-2 border-bottom">
          <strong class="text-uppercase small">Notificaciones</strong>
          <a class="small enlace-rojo" href="#/notificaciones">Ver todas</a>
        </div>
        <div data-panel-notificaciones>
          ${itemsPanel()}
        </div>
        ${
          contador
            ? `<div class="border-top text-center">
                 <button class="dropdown-item small py-2" type="button" data-leer-todas>
                   <i class="bi bi-check2-all"></i> Marcar todas como leídas
                 </button>
               </div>`
            : ""
        }
      </div>
    </div>
    <a class="btn btn-sm btn-fantasma d-flex align-items-center gap-2" href="#/perfil">
      ${avatar(usuario.username)}
      <span>${escapar(usuario.username)}</span>
      ${usuario.rol === "admin" ? '<span class="badge text-bg-rojo">admin</span>' : ""}
    </a>
    <button class="btn btn-sm btn-fantasma" type="button" data-cerrar-sesion>
      <i class="bi bi-box-arrow-right"></i> Salir
    </button>`;

  const navAdmin = elemento("nav-admin");
  const navNuevo = elemento("nav-nuevo-torneo");
  navAdmin?.classList.toggle("d-none", !esAdmin());
  navNuevo?.classList.toggle("d-none", !esAdmin());
}

function itemsPanel() {
  if (!resumen.recientes.length) {
    return '<div class="px-3 py-4 text-center text-secundario small">No tenés notificaciones.</div>';
  }
  return resumen.recientes
    .map(
      (notificacion) => `
      <button class="notificacion-mini ${notificacion.leida ? "" : "sin-leer"}" type="button"
              data-notificacion="${notificacion.id}">
        <span class="notificacion-icono"><i class="bi bi-${iconoNotificacion(
          notificacion.tipo
        )}"></i></span>
        <span class="flex-grow-1 text-start min-w-0">
          <span class="d-block small fw-semibold">${escapar(notificacion.titulo)}</span>
          <span class="d-block text-secundario notificacion-texto">${escapar(
            notificacion.mensaje
          )}</span>
          <span class="d-block text-secundario notificacion-fecha">${fechaRelativa(
            notificacion.creada_en
          )}</span>
        </span>
      </button>`
    )
    .join("");
}

function actualizarPanel() {
  const contador = document.querySelector(".campana-contador");
  if (contador) {
    contador.textContent = resumen.sin_leer || 0;
    contador.classList.toggle("d-none", !resumen.sin_leer);
  }
  const panel = document.querySelector("[data-panel-notificaciones]");
  if (panel) panel.innerHTML = itemsPanel();
}

function sonar() {
  const audio = elemento("faceitAlert");
  if (!audio) return;
  try {
    audio.currentTime = 0;
    audio.volume = 0.8;
    audio.play().catch(() => {});
  } catch (_error) {
    // Algunos navegadores bloquean el audio hasta la primera interacción.
  }
}

function alTenerAudio() {
  if (audioListo) return;
  audioListo = true;
  const audio = elemento("faceitAlert");
  audio?.play().then(() => {
    if (audio) audio.pause();
  }).catch(() => {});
  window.removeEventListener("pointerdown", alTenerAudio);
}

export function toast(mensaje, { titulo = "ArenaGG", url = null, textoAccion = "Ver", tipo = "bell" } = {}) {
  const contenedor = elemento("toastStack");
  if (!contenedor) return;

  const nodo = document.createElement("div");
  nodo.className = "toast-faceit";
  nodo.innerHTML = `
    <span class="toast-faceit-icono"><i class="bi bi-${iconoNotificacion(tipo)}"></i></span>
    <div class="flex-grow-1 min-w-0">
      <div class="toast-faceit-titulo">${escapar(titulo)}</div>
      <div class="toast-faceit-mensaje">${escapar(mensaje)}</div>
      ${
        url
          ? `<a class="toast-faceit-accion d-inline-block" href="${escapar(url)}">${escapar(
              textoAccion
            )} <i class="bi bi-arrow-right"></i></a>`
          : ""
      }
    </div>
    <button class="btn-close btn-close-white" type="button" aria-label="Cerrar"></button>`;

  nodo.querySelector("button")?.addEventListener("click", () => nodo.remove());
  contenedor.appendChild(nodo);
  requestAnimationFrame(() => nodo.classList.add("visible"));

  const vida = url ? 9000 : 6000;
  setTimeout(() => {
    nodo.classList.remove("visible");
    setTimeout(() => nodo.remove(), 260);
  }, vida);
}

export async function refrescarNotificaciones({ silencioso = false } = {}) {
  if (!estaAutenticado() || cargandoResumen) return;
  cargandoResumen = true;
  try {
    const datos = await api.get("/notificaciones/resumen");
    const nuevas = idsConocidos
      ? datos.recientes.filter(
          (notificacion) => !notificacion.leida && !idsConocidos.has(notificacion.id)
        )
      : [];
    idsConocidos = new Set(datos.recientes.map((notificacion) => notificacion.id));
    resumen = datos;
    actualizarPanel();

    if (!silencioso && nuevas.length) {
      nuevas
        .slice()
        .reverse()
        .forEach((notificacion) => {
          toast(notificacion.mensaje || notificacion.titulo, {
            titulo: notificacion.titulo,
            url: notificacion.url,
            tipo: notificacion.tipo,
          });
        });
      if (nuevas.some((notificacion) => ["partida", "resultado", "campeon", "disputa"].includes(notificacion.tipo))) {
        sonar();
      }
    }
  } catch (error) {
    if (error.status !== 401 && !silencioso) {
      toast(error.detalle || "No se pudieron actualizar las notificaciones.", {
        titulo: "Notificaciones",
        tipo: "disputa",
      });
    }
  } finally {
    cargandoResumen = false;
  }
}

function iniciarPolling() {
  detenerPolling();
  if (!estaAutenticado()) return;
  temporizador = setInterval(() => {
    refrescarNotificaciones();
  }, INTERVALO);
}

function detenerPolling() {
  if (temporizador) {
    clearInterval(temporizador);
    temporizador = null;
  }
}

async function abrirNotificacion(id) {
  const notificacion = resumen.recientes.find((item) => item.id === Number(id));
  try {
    if (notificacion && !notificacion.leida) {
      const respuesta = await api.post(`/notificaciones/${id}/leer`);
      resumen.sin_leer = respuesta.sin_leer;
      resumen.recientes = resumen.recientes.map((item) =>
        item.id === Number(id) ? respuesta.notificacion : item
      );
      actualizarPanel();
    }
    const destino = notificacion?.url
      ? notificacion.url.startsWith("#")
        ? notificacion.url
        : `#${notificacion.url}`
      : "#/notificaciones";
    window.location.hash = destino;
  } catch (error) {
    toast(error.detalle || "No se pudo abrir la notificación.", { tipo: "disputa" });
  }
}

async function marcarTodas() {
  try {
    await api.post("/notificaciones/leer-todas");
    await refrescarNotificaciones({ silencioso: true });
    toast("Todas las notificaciones quedaron como leídas.", { titulo: "Bandeja al día", tipo: "resultado" });
  } catch (error) {
    toast(error.detalle || "No se pudieron marcar las notificaciones.", { tipo: "disputa" });
  }
}

export function actualizarActivo(ruta) {
  document.querySelectorAll("[data-ruta]").forEach((enlace) => {
    const destino = enlace.dataset.ruta;
    const activo =
      ruta === destino ||
      (destino !== "/" && ruta.startsWith(`${destino}/`)) ||
      (destino === "/torneos" && ruta.startsWith("/torneos"));
    enlace.classList.toggle("active", activo);
  });
}

export function cerrarMenu() {
  const menu = elemento("menu");
  if (!menu || !menu.classList.contains("show")) return;
  const Colapsable = window.bootstrap?.Collapse;
  if (Colapsable) Colapsable.getOrCreateInstance(menu).hide();
}

function manejarSesion(evento) {
  renderZonaUsuario();
  if (estaAutenticado()) {
    idsConocidos = null;
    refrescarNotificaciones({ silencioso: true });
    iniciarPolling();
  } else {
    detenerPolling();
    resumen = { sin_leer: 0, recientes: [] };
    idsConocidos = null;
  }
  if (evento.detail?.motivo === "expirada") {
    window.location.hash = "#/login";
  }
}

export function iniciarLayout() {
  renderZonaUsuario();
  if (estaAutenticado()) {
    refrescarNotificaciones({ silencioso: true });
    iniciarPolling();
  }

  zonaUsuario()?.addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-notificacion]");
    if (boton) {
      abrirNotificacion(boton.dataset.notificacion);
      return;
    }
    if (evento.target.closest("[data-leer-todas]")) {
      marcarTodas();
      return;
    }
    if (evento.target.closest("[data-cerrar-sesion]")) {
      cerrarSesion({ motivo: "manual" });
      toast("Cerraste sesión. Nos vemos en la arena.", { titulo: "Hasta pronto", tipo: "bye" });
      window.location.hash = "#/";
    }
  });

  window.addEventListener("arenagg:sesion", manejarSesion);
  window.addEventListener("arenagg:aviso", (evento) => {
    if (evento.detail?.mensaje) {
      toast(evento.detail.mensaje, { titulo: "Sesión", tipo: "disputa" });
    }
  });
  window.addEventListener("pointerdown", alTenerAudio, { once: true });
}
