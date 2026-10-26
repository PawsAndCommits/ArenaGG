import { api } from "../api.js";
import { estaAutenticado, usuarioActual } from "../auth.js";
import {
  badgeEstadoTorneo,
  bannerCampeon,
  bracket,
  estadoVacio,
  listaParticipantes,
  tablaPosiciones,
} from "../components.js";
import { refrescarNotificaciones, toast } from "../layout.js";
import {
  confirmar,
  escapar,
  fechaHora,
  mensajeError,
  resumenErrores,
} from "../utils.js";

const TABS = [
  ["resumen", "Resumen", "file-text"],
  ["participantes", "Participantes", "people"],
  ["llave", "Llave", "diagram-3"],
  ["posiciones", "Posiciones", "table"],
];

function panelInscripcion(torneo) {
  const usuario = usuarioActual();

  if (!estaAutenticado()) {
    return `
      <div class="panel-accion">
        <h2 class="h5"><i class="bi bi-door-open"></i> Tu lugar en el torneo</h2>
        <p class="text-secundario small">Iniciá sesión para inscribirte y seguir tus partidas.</p>
        <a class="btn btn-rojo w-100" href="#/login?redirect=${encodeURIComponent(
          `/torneos/${torneo.id}`
        )}">Iniciar sesión</a>
      </div>`;
  }

  const inscripcion = torneo.mi_inscripcion;
  if (torneo.es_organizador && !inscripcion) {
    return `
      <div class="panel-accion">
        <span class="chip chip-sm mb-2"><i class="bi bi-shield-check"></i> Organizás este torneo</span>
        <h2 class="h5 mb-1">Panel del organizador</h2>
        <p class="text-secundario small">Gestioná la llave, los resultados y la programación desde acá.</p>
        <a class="btn btn-sm btn-fantasma w-100" href="#/torneos/${torneo.id}/editar">
          <i class="bi bi-pencil-square"></i> Editar torneo
        </a>
      </div>`;
  }
  if (inscripcion) {
    const esCapitan =
      !inscripcion.equipo_id ||
      inscripcion.equipo?.capitan_id === usuario?.id;
    const puedeCancelar =
      esCapitan &&
      !torneo.tiene_partidas &&
      ["proximamente", "inscripciones_abiertas"].includes(torneo.estado);
    return `
      <div class="panel-accion">
        <span class="chip chip-sm mb-2"><i class="bi bi-check-circle"></i> Estás inscripto</span>
        <h2 class="h5 mb-1">${escapar(inscripcion.nombre)}</h2>
        <div class="roster-mini mb-3">
          ${(inscripcion.roster || [])
            .map((jugador) => `<span>${escapar(jugador.username)}</span>`)
            .join("")}
        </div>
        ${
          inscripcion.equipo_id
            ? `<a class="btn btn-sm btn-fantasma w-100 mb-2" href="#/equipos/${inscripcion.equipo_id}">
                 <i class="bi bi-shield-shaded"></i> Ver equipo
               </a>`
            : ""
        }
        ${
          puedeCancelar
            ? `<button class="btn btn-sm btn-outline-danger w-100" type="button" data-cancelar>
                 <i class="bi bi-x-circle"></i> Cancelar inscripción
               </button>`
            : `<p class="text-secundario small mb-0">${
                !esCapitan
                  ? "Solo el capitán puede cancelar la inscripción del equipo."
                  : "La inscripción ya está cerrada."
              }</p>`
        }
      </div>`;
  }

  if (!torneo.acepta_inscripciones) {
    return `
      <div class="panel-accion">
        <h2 class="h5"><i class="bi bi-lock"></i> Inscripciones cerradas</h2>
        <p class="text-secundario small mb-0">${
          torneo.esta_completo ? "El torneo está completo." : "Este torneo ya no recibe inscripciones."
        }</p>
      </div>`;
  }

  if (torneo.modalidad === "equipos") {
    const equipos = torneo.mis_equipos || [];
    if (!equipos.length) {
      const cantidad = torneo.jugadores_por_equipo || "los";
      return `
        <div class="panel-accion">
          <h2 class="h5"><i class="bi bi-people"></i> Inscripción por equipos</h2>
          <p class="text-secundario small">Necesitás un equipo con ${cantidad} integrantes activos y ser su capitán.</p>
          <a class="btn btn-rojo w-100" href="#/equipos"><i class="bi bi-shield-shaded"></i> Ir a mis equipos</a>
        </div>`;
    }
    return `
      <div class="panel-accion">
        <h2 class="h5"><i class="bi bi-people"></i> Inscribir mi equipo</h2>
        <p class="text-secundario small">Elegí un equipo con ${torneo.jugadores_por_equipo} integrantes activos.</p>
        <label class="form-label small" for="equipoInscripcion">Equipo</label>
        <select class="form-select mb-3" id="equipoInscripcion">
          ${equipos
            .map(
              (equipo) =>
                `<option value="${equipo.id}">${escapar(equipo.nombre)} (${equipo.miembros} jugadores)</option>`
            )
            .join("")}
        </select>
        <button class="btn btn-rojo w-100" type="button" data-inscribirse>
          <i class="bi bi-clipboard-check"></i> Inscribir equipo
        </button>
      </div>`;
  }

  return `
    <div class="panel-accion">
      <h2 class="h5"><i class="bi bi-person-plus"></i> Inscribite</h2>
      <p class="text-secundario small">Quedan ${torneo.cupos_disponibles} cupos disponibles.</p>
      <button class="btn btn-rojo w-100" type="button" data-inscribirse>
        <i class="bi bi-clipboard-check"></i> Confirmar inscripción
      </button>
    </div>`;
}

function panelAdmin(torneo) {
  if (!torneo.puede_gestionar) return "";
  return `
    <div class="panel-accion mt-3">
      <h2 class="h6 text-uppercase text-secundario mb-3"><i class="bi bi-shield-lock"></i> Organización</h2>
      <div class="d-grid gap-2">
        <a class="btn btn-sm btn-fantasma" href="#/torneos/${torneo.id}/editar">
          <i class="bi bi-pencil-square"></i> Editar torneo
        </a>
        ${
          torneo.estado === "inscripciones_abiertas"
            ? `<button class="btn btn-sm btn-rojo" type="button" data-iniciar ${
                torneo.inscriptos < 2 ? "disabled" : ""
              }><i class="bi bi-play-fill"></i> Iniciar llave</button>`
            : ""
        }
        ${
          torneo.estado === "en_curso"
            ? `<button class="btn btn-sm btn-outline-warning" type="button" data-finalizar>
                 <i class="bi bi-flag-fill"></i> Finalizar torneo
               </button>`
            : ""
        }
        ${
          torneo.tiene_partidas
            ? `<button class="btn btn-sm btn-outline-warning" type="button" data-reiniciar>
                 <i class="bi bi-arrow-counterclockwise"></i> Reiniciar llave
               </button>`
            : ""
        }
        <button class="btn btn-sm btn-outline-danger" type="button" data-eliminar>
          <i class="bi bi-trash"></i> Eliminar torneo
        </button>
      </div>
    </div>`;
}

function contenidoTab(tab, datos) {
  const { torneo, participantes, partidas, posiciones } = datos;
  if (tab === "participantes") {
    return listaParticipantes(participantes.participantes || []);
  }
  if (tab === "llave") {
    return bracket(partidas.partidas || [], torneo.id);
  }
  if (tab === "posiciones") {
    return tablaPosiciones(posiciones.posiciones || []);
  }
  return `
    <div class="row g-3">
      <div class="col-md-7">
        <h3 class="h6 text-uppercase text-secundario">Descripción</h3>
        <p>${torneo.descripcion ? escapar(torneo.descripcion) : "Sin descripción."}</p>
        <h3 class="h6 text-uppercase text-secundario mt-4">Reglas</h3>
        <p class="mb-0" style="white-space: pre-line">${
          torneo.reglas ? escapar(torneo.reglas) : "Las reglas se comunican en la sala de la partida."
        }</p>
      </div>
      <div class="col-md-5">
        <div class="resultado-caja">
          <div class="meta meta-grande flex-column align-items-start gap-2">
            <span><i class="bi bi-calendar-event"></i> ${fechaHora(torneo.fecha)}</span>
            <span><i class="bi bi-people"></i> ${escapar(torneo.modalidad_texto)}${
              torneo.jugadores_por_equipo ? ` · ${torneo.jugadores_por_equipo} por equipo` : ""
            }</span>
            <span><i class="bi bi-collection"></i> ${escapar(torneo.formato_texto)}</span>
            <span><i class="bi bi-trophy"></i> ${escapar(torneo.premio || "Premio a definir")}</span>
            ${
              torneo.creado_por
                ? `<span><i class="bi bi-person-badge"></i> Organiza ${escapar(torneo.creado_por)}</span>`
                : ""
            }
          </div>
        </div>
      </div>
    </div>`;
}

export async function render(contenedor, { params, query, ruta }) {
  const torneoId = params.id;
  let tabActivo = TABS.some(([clave]) => clave === query.get("tab"))
    ? query.get("tab")
    : "resumen";

  async function cargar() {
    const [torneo, participantes, partidas, posiciones] = await Promise.all([
      api.get(`/torneos/${torneoId}`),
      api.get(`/torneos/${torneoId}/participantes`),
      api.get(`/torneos/${torneoId}/partidas`),
      api.get(`/torneos/${torneoId}/posiciones`),
    ]);
    return { torneo, participantes, partidas, posiciones };
  }

  function pintar(datos) {
    const { torneo, participantes, partidas, posiciones } = datos;
    const miPartida = torneo.mi_partida;
    contenedor.innerHTML = `
      <div class="container">
        <a class="enlace-rojo small d-inline-block mb-3" href="#/torneos">
          <i class="bi bi-arrow-left"></i> Volver a torneos
        </a>

        <div class="tarjeta torneo-cabecera mb-4">
          <div class="row g-4">
            <div class="col-lg-8">
              <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
                <span class="juego"><i class="bi bi-joystick"></i> ${escapar(torneo.videojuego)}</span>
                ${badgeEstadoTorneo(torneo)}
                ${torneo.destacado ? '<span class="estado estado-destacado"><i class="bi bi-star-fill"></i> Destacado</span>' : ""}
              </div>
              <h1 class="torneo-titulo">${escapar(torneo.nombre)}</h1>
              <div class="meta meta-grande">
                <span><i class="bi bi-calendar-event"></i> ${fechaHora(torneo.fecha)}</span>
                <span><i class="bi bi-${
                  torneo.modalidad === "equipos" ? "people" : "person"
                }"></i> ${escapar(torneo.modalidad_texto)}</span>
                <span><i class="bi bi-collection"></i> ${escapar(torneo.formato_texto)}</span>
                <span><i class="bi bi-trophy"></i> ${escapar(torneo.premio || "Premio a definir")}</span>
              </div>
              <div class="mt-3">
                <div class="d-flex justify-content-between small mb-1">
                  <span>${torneo.inscriptos}/${torneo.cupo_maximo} inscriptos</span>
                  <span class="${torneo.esta_completo ? "text-danger" : "text-rojo"}">
                    ${torneo.esta_completo ? "Completo" : `${torneo.cupos_disponibles} cupos libres`}
                  </span>
                </div>
                <div class="progress progress-fino">
                  <div class="progress-bar barra-roja" style="width: ${torneo.porcentaje_ocupado}%"></div>
                </div>
              </div>
            </div>
            <div class="col-lg-4">
              <div class="panel-accion h-100 d-flex flex-column justify-content-center">
                <div class="cifra mb-3">
                  <i class="bi bi-people"></i>
                  <div class="cifra-valor">${torneo.inscriptos}</div>
                  <div class="cifra-texto">Participantes confirmados</div>
                </div>
                <div class="cifra">
                  <i class="bi bi-diagram-3"></i>
                  <div class="cifra-valor">${partidas.partidas?.length || 0}</div>
                  <div class="cifra-texto">Partidas en la llave</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        ${bannerCampeon(torneo.campeon)}

        ${
          miPartida
            ? `<div class="mi-partida mb-4">
                 <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
                   <span class="chip chip-sm"><i class="bi bi-controller"></i> Tu próxima partida</span>
                   <span class="text-secundario small">${escapar(miPartida.nombre_ronda)} · #${miPartida.numero}</span>
                 </div>
                 <div class="mi-partida-vs">
                   <div class="mi-partida-nombre text-end">${escapar(miPartida.participante1?.nombre || "Por definir")}</div>
                   <span class="vs">VS</span>
                   <div class="mi-partida-nombre">${escapar(miPartida.participante2?.nombre || "Por definir")}</div>
                 </div>
                 <div class="text-center mt-2">
                   <a class="btn btn-sm btn-rojo mt-2" href="#/torneos/${torneo.id}/partidas/${miPartida.id}">
                     <i class="bi bi-controller"></i> Entrar a la sala
                   </a>
                 </div>
               </div>`
            : ""
        }

        <div class="row g-4">
          <div class="col-lg-8">
            <ul class="nav nav-tabs pestanas mb-3">
              ${TABS.map(
                ([clave, texto, icono]) => `
                <li class="nav-item">
                  <button class="nav-link ${tabActivo === clave ? "active" : ""}" type="button" data-tab="${clave}">
                    <i class="bi bi-${icono}"></i> ${texto}
                  </button>
                </li>`
              ).join("")}
            </ul>
            <div data-panel-tab>${contenidoTab(tabActivo, datos)}</div>
          </div>
          <div class="col-lg-4">
            ${panelInscripcion(torneo)}
            ${panelAdmin(torneo)}
            ${
              torneo.total_rondas
                ? `<div class="tarjeta mt-3">
                     <div class="meta flex-column align-items-start gap-2">
                       <span><i class="bi bi-diagram-3"></i> ${torneo.total_rondas} rondas</span>
                       <span><i class="bi bi-play-circle"></i> Inició ${fechaHora(torneo.iniciado_en)}</span>
                     </div>
                   </div>`
                : ""
            }
          </div>
        </div>
      </div>`;

    contenedor.querySelectorAll("[data-tab]").forEach((boton) => {
      boton.addEventListener("click", () => {
        tabActivo = boton.dataset.tab;
        contenedor.querySelectorAll("[data-tab]").forEach((otro) => {
          otro.classList.toggle("active", otro.dataset.tab === tabActivo);
        });
        const panel = contenedor.querySelector("[data-panel-tab]");
        if (panel) panel.innerHTML = contenidoTab(tabActivo, datos);
        window.history.replaceState(null, "", `#${ruta}?tab=${tabActivo}`);
      });
    });

    const recargar = async (mensaje) => {
      const nuevos = await cargar();
      pintar(nuevos);
      refrescarNotificaciones({ silencioso: true });
      if (mensaje) toast(mensaje, { titulo: "Torneo", tipo: "resultado" });
    };

    const ejecutar = async (boton, accion, mensaje) => {
      if (boton) boton.disabled = true;
      try {
        await accion();
        await recargar(mensaje);
      } catch (error) {
        toast(resumenErrores(error).join(" · "), { titulo: "No se pudo completar", tipo: "disputa" });
        if (boton) boton.disabled = false;
      }
    };

    contenedor.querySelector("[data-inscribirse]")?.addEventListener("click", (evento) => {
      const boton = evento.currentTarget;
      const selector = contenedor.querySelector("#equipoInscripcion");
      const cuerpo = selector ? { equipo_id: Number(selector.value) } : undefined;
      ejecutar(boton, () => api.post(`/torneos/${torneo.id}/inscribirse`, cuerpo), "Inscripción confirmada.");
    });

    contenedor.querySelector("[data-cancelar]")?.addEventListener("click", (evento) => {
      if (!confirmar("¿Cancelar tu inscripción en este torneo?", "Sí, cancelar")) return;
      ejecutar(
        evento.currentTarget,
        () => api.delete(`/torneos/${torneo.id}/inscribirse`),
        "Inscripción cancelada."
      );
    });

    contenedor.querySelector("[data-iniciar]")?.addEventListener("click", (evento) => {
      if (!confirmar("Se generará la llave y el torneo comenzará.", "Iniciar torneo")) return;
      ejecutar(evento.currentTarget, () => api.post(`/torneos/${torneo.id}/iniciar`), "Torneo iniciado.");
    });

    contenedor.querySelector("[data-reiniciar]")?.addEventListener("click", (evento) => {
      if (!confirmar("Se borrarán las partidas y volverán a abrirse las inscripciones.", "Reiniciar llave")) return;
      ejecutar(evento.currentTarget, () => api.post(`/torneos/${torneo.id}/reiniciar`), "Llave reiniciada.");
    });

    contenedor.querySelector("[data-finalizar]")?.addEventListener("click", (evento) => {
      if (!confirmar("El torneo se marcará como finalizado y no admitirá más cambios de estado.", "Finalizar torneo")) return;
      ejecutar(evento.currentTarget, () => api.post(`/torneos/${torneo.id}/finalizar`), "Torneo finalizado.");
    });

    contenedor.querySelector("[data-eliminar]")?.addEventListener("click", async (evento) => {
      if (!confirmar(`¿Eliminar «${torneo.nombre}»? Esta acción no se puede deshacer.`, "Eliminar")) return;
      const boton = evento.currentTarget;
      boton.disabled = true;
      try {
        await api.delete(`/torneos/${torneo.id}`);
        toast("Torneo eliminado.", { titulo: "Torneo", tipo: "resultado" });
        window.location.hash = "#/torneos";
      } catch (error) {
        toast(resumenErrores(error).join(" · "), { titulo: "No se pudo eliminar", tipo: "disputa" });
        boton.disabled = false;
      }
    });
  }

  pintar(await cargar());
}
