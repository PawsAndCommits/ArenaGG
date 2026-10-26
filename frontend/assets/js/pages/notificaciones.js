import { api } from "../api.js";
import { paginacion, estadoVacio } from "../components.js";
import { refrescarNotificaciones, toast } from "../layout.js";
import {
  escapar,
  fechaHora,
  iconoNotificacion,
  resumenErrores,
} from "../utils.js";

const FILTROS = [
  ["todas", "Todas", "bell"],
  ["sin_leer", "Sin leer", "envelope"],
];

export async function render(contenedor, { query }) {
  let filtro = query.get("filtro") === "sin_leer" ? "sin_leer" : "todas";
  let pagina = Math.max(1, Number(query.get("pagina")) || 1);
  let datos = null;

  async function cargar() {
    datos = await api.get("/notificaciones", { filtro, pagina, por_pagina: 15 });
    if (datos.paginas && pagina > datos.paginas) {
      pagina = datos.paginas;
      datos = await api.get("/notificaciones", { filtro, pagina, por_pagina: 15 });
    }
    return datos;
  }

  function item(notificacion) {
    return `
      <button class="notif-fila ${notificacion.leida ? "leida" : "sin-leer"}" type="button"
              data-notificacion="${notificacion.id}">
        <span class="notificacion-icono">
          <i class="bi bi-${iconoNotificacion(notificacion.tipo)}"></i>
        </span>
        <span class="flex-grow-1 min-w-0">
          <span class="d-flex flex-wrap align-items-center gap-2">
            <strong class="small">${escapar(notificacion.titulo)}</strong>
            ${notificacion.torneo_id ? '<span class="chip chip-sm">Torneo</span>' : ""}
          </span>
          <span class="d-block text-secundario small mt-1">${escapar(notificacion.mensaje)}</span>
          <span class="d-block text-secundario notificacion-fecha mt-1">
            ${fechaHora(notificacion.creada_en)}
          </span>
        </span>
        <span class="notif-punto" aria-hidden="true"></span>
      </button>`;
  }

  function pintar() {
    const items = datos.items || [];
    contenedor.innerHTML = `
      <div class="container">
        <div class="cabecera-pagina d-flex flex-column flex-md-row justify-content-between align-items-md-end gap-3">
          <div>
            <h1><i class="bi bi-bell"></i> Notificaciones</h1>
            <p class="text-secundario mb-0">
              ${datos.sin_leer
                ? `Tenés ${datos.sin_leer} notificación${datos.sin_leer === 1 ? "" : "es"} sin leer.`
                : "Estás al día."}
            </p>
          </div>
          <button class="btn btn-fantasma" type="button" data-leer-todas ${datos.sin_leer ? "" : "disabled"}>
            <i class="bi bi-check2-all"></i> Marcar todas como leídas
          </button>
        </div>

        <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
          <div class="d-flex gap-2">
            ${FILTROS.map(
              ([valor, texto, icono]) => `
              <button class="btn btn-sm ${filtro === valor ? "btn-rojo" : "btn-fantasma"}"
                      type="button" data-filtro="${valor}">
                <i class="bi bi-${icono}"></i> ${texto}
              </button>`
            ).join("")}
          </div>
          <span class="text-secundario small">
            ${datos.total} notificación${datos.total === 1 ? "" : "es"}
          </span>
        </div>

        <div class="tarjeta overflow-hidden">
          ${
            items.length
              ? items.map(item).join("")
              : `<div class="py-5">${estadoVacio("inbox", "No hay notificaciones en esta bandeja.")}</div>`
          }
        </div>

        <div data-paginacion>${paginacion(pagina, datos.paginas)}</div>
      </div>`;

    contenedor.querySelectorAll("[data-filtro]").forEach((boton) => {
      boton.addEventListener("click", async () => {
        filtro = boton.dataset.filtro;
        pagina = 1;
        await recargar();
      });
    });

    contenedor.querySelector("[data-leer-todas]")?.addEventListener("click", async (evento) => {
      const boton = evento.currentTarget;
      boton.disabled = true;
      try {
        await api.post("/notificaciones/leer-todas");
        await recargar();
        refrescarNotificaciones({ silencioso: true });
        toast("Todas las notificaciones quedaron como leídas.", {
          titulo: "Bandeja al día",
          tipo: "resultado",
        });
      } catch (error) {
        toast(resumenErrores(error).join(" · "), {
          titulo: "No se pudo completar",
          tipo: "disputa",
        });
        boton.disabled = false;
      }
    });

    contenedor.querySelectorAll("[data-notificacion]").forEach((boton) => {
      boton.addEventListener("click", () => abrir(boton));
    });

    contenedor.querySelectorAll("[data-pagina]").forEach((boton) => {
      if (boton.closest(".disabled")) return;
      boton.addEventListener("click", async () => {
        pagina = Math.max(1, Number(boton.dataset.pagina));
        await recargar();
      });
    });
  }

  async function recargar() {
    await cargar();
    pintar();
    window.history.replaceState(
      null,
      "",
      `#/notificaciones?filtro=${filtro}&pagina=${pagina}`
    );
  }

  async function abrir(boton) {
    const id = Number(boton.dataset.notificacion);
    const notificacion = (datos.items || []).find((itemActual) => itemActual.id === id);
    if (!notificacion) return;

    boton.disabled = true;
    try {
      if (!notificacion.leida) {
        await api.post(`/notificaciones/${id}/leer`);
        refrescarNotificaciones({ silencioso: true });
      }
      if (notificacion.url) {
        window.location.hash = notificacion.url.startsWith("#")
          ? notificacion.url
          : `#${notificacion.url}`;
      } else {
        toast(notificacion.mensaje || notificacion.titulo, {
          titulo: notificacion.titulo,
          tipo: notificacion.tipo,
        });
        await recargar();
      }
    } catch (error) {
      toast(resumenErrores(error).join(" · "), {
        titulo: "No se pudo abrir",
        tipo: "disputa",
      });
      boton.disabled = false;
    }
  }

  await cargar();
  pintar();
}
