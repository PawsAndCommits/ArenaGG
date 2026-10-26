import { api } from "../api.js";
import { esAdmin, estaAutenticado, usuarioActual } from "../auth.js";
import { avatar, escudo, estadoVacio } from "../components.js";
import { refrescarNotificaciones, toast } from "../layout.js";
import {
  confirmar,
  escapar,
  fechaCorta,
  resumenErrores,
} from "../utils.js";

const ESTADOS = {
  proximamente: "Próximamente",
  inscripciones_abiertas: "Inscripciones abiertas",
  en_curso: "En curso",
  finalizado: "Finalizado",
};

export async function render(contenedor, { params }) {
  const equipoId = Number(params.id);
  let equipo = null;
  let disponibles = [];

  async function cargar() {
    equipo = await api.get(`/equipos/${equipoId}`);
    disponibles = [];
    if (equipo.mi_rol === "capitan") {
      try {
        disponibles = await api.get(`/equipos/${equipoId}/torneos-disponibles`);
      } catch (_error) {
        disponibles = [];
      }
    }
    return { equipo, disponibles };
  }

  function filaRoster(miembro) {
    const esCapitanEquipo = miembro.rol === "capitan";
    const puedeGestionar = equipo.mi_rol === "capitan";
    return `
      <div class="roster-fila">
        ${avatar(miembro.username)}
        <div class="flex-grow-1 min-w-0">
          <a class="enlace-jugador" href="#/usuarios/${miembro.usuario_id}">${escapar(miembro.username)}</a>
          <div class="text-secundario small">Desde ${fechaCorta(miembro.creado_en)}</div>
        </div>
        <span class="rol-etiqueta ${esCapitanEquipo ? "capitan" : ""}">
          ${esCapitanEquipo ? "Capitán" : "Jugador"}
        </span>
        ${
          puedeGestionar && !esCapitanEquipo
            ? `<div class="d-flex gap-1">
                 <button class="btn btn-sm btn-fantasma" type="button" title="Transferir capitanía"
                         data-transferir="${miembro.usuario_id}">
                   <i class="bi bi-star"></i>
                 </button>
                 <button class="btn btn-sm btn-outline-danger" type="button" title="Quitar del equipo"
                         data-expulsar="${miembro.id}">
                   <i class="bi bi-person-dash"></i>
                 </button>
               </div>`
            : ""
        }
      </div>`;
  }

  function panelInvitaciones() {
    if (equipo.mi_rol !== "capitan" || !equipo.invitaciones.length) return "";
    return `
      <div class="tarjeta mt-3">
        <h2 class="h6 text-uppercase text-secundario mb-3">
          <i class="bi bi-envelope"></i> Invitaciones enviadas
        </h2>
        <div class="roster-lista">
          ${equipo.invitaciones
            .map(
              (invitacion) => `
            <div class="roster-fila">
              ${avatar(invitacion.username)}
              <div class="flex-grow-1">
                <div class="fw-semibold">${escapar(invitacion.username)}</div>
                <div class="text-secundario small">Enviada ${fechaCorta(invitacion.creado_en)}</div>
              </div>
              <span class="chip chip-sm">Pendiente</span>
            </div>`
            )
            .join("")}
        </div>
      </div>`;
  }

  function panelTorneos() {
    if (equipo.mi_rol !== "capitan") return "";
    if (!disponibles.length) {
      return `
        <div class="tarjeta mt-3">
          <h2 class="h6 text-uppercase text-secundario mb-3">
            <i class="bi bi-trophy"></i> Torneos disponibles
          </h2>
          <p class="text-secundario small mb-0">No hay torneos por equipos con inscripciones abiertas.</p>
        </div>`;
    }
    return `
      <div class="tarjeta mt-3">
        <h2 class="h6 text-uppercase text-secundario mb-3">
          <i class="bi bi-trophy"></i> Inscribir en un torneo
        </h2>
        <div class="d-flex flex-column gap-2">
          ${disponibles
            .map((torneo) => {
              const completo = equipo.miembros !== torneo.jugadores_por_equipo;
              return `
                <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 pb-2 border-bottom">
                  <div class="min-w-0">
                    <a class="enlace-jugador" href="#/torneos/${torneo.id}">${escapar(torneo.nombre)}</a>
                    <div class="text-secundario small">
                      ${escapar(torneo.videojuego)} · ${torneo.jugadores_por_equipo} por equipo ·
                      ${torneo.cupos_disponibles} cupos libres
                      ${completo ? " · el roster no coincide" : ""}
                    </div>
                  </div>
                  <button class="btn btn-sm btn-rojo" type="button" data-inscribir="${torneo.id}"
                          ${completo ? "disabled" : ""}>
                    <i class="bi bi-clipboard-check"></i> Inscribir
                  </button>
                </div>`;
            })
            .join("")}
        </div>
      </div>`;
  }

  function pintar() {
    const usuario = usuarioActual();
    const esCapitan = equipo.mi_rol === "capitan";
    const esMiembroActivo = Boolean(equipo.mi_rol && equipo.mi_rol !== "invitado" && equipo.mi_rol !== "rechazado");
    const puedeEditar = esCapitan || esAdmin();

    contenedor.innerHTML = `
      <div class="container">
        <a class="enlace-rojo small d-inline-block mb-3" href="#/equipos">
          <i class="bi bi-arrow-left"></i> Volver a equipos
        </a>

        <div class="tarjeta equipo-cabecera mb-4">
          <div class="d-flex flex-column flex-lg-row align-items-lg-center gap-3">
            ${escudo(equipo.nombre, { iniciales: equipo.iniciales, tamano: "escudo-xl" })}
            <div class="flex-grow-1 min-w-0">
              <div class="d-flex flex-wrap align-items-center gap-2 mb-1">
                <h1 class="h2 mb-0">${escapar(equipo.nombre)}</h1>
                ${equipo.tag ? `<span class="chip chip-sm">${escapar(equipo.tag)}</span>` : ""}
                ${esCapitan ? '<span class="estado estado-inscripciones_abiertas">Capitán</span>' : ""}
              </div>
              <div class="meta">
                <span><i class="bi bi-person-badge"></i> ${escapar(equipo.capitan || "Sin capitán")}</span>
                <span><i class="bi bi-people"></i> ${equipo.miembros} integrante${equipo.miembros === 1 ? "" : "s"}</span>
                <span><i class="bi bi-calendar3"></i> Creado ${fechaCorta(equipo.creado_en)}</span>
              </div>
              ${
                equipo.descripcion
                  ? `<p class="text-secundario mt-2 mb-0">${escapar(equipo.descripcion)}</p>`
                  : ""
              }
            </div>
            ${
              puedeEditar
                ? `<div class="d-flex flex-wrap gap-2">
                     <a class="btn btn-fantasma" href="#/equipos/${equipo.id}/editar">
                       <i class="bi bi-pencil-square"></i> Editar
                     </a>
                     <button class="btn btn-outline-danger" type="button" data-eliminar>
                       <i class="bi bi-trash"></i> Eliminar
                     </button>
                   </div>`
                : ""
            }
          </div>
        </div>

        <div class="row g-4">
          <div class="col-lg-7">
            <div class="tarjeta">
              <div class="d-flex justify-content-between align-items-center mb-3">
                <h2 class="h5 mb-0"><i class="bi bi-people"></i> Roster</h2>
                <span class="text-secundario small">${equipo.miembros} activos</span>
              </div>
              <div class="roster-lista">
                ${equipo.roster.map(filaRoster).join("")}
              </div>
            </div>

            ${
              esCapitan
                ? `<div class="tarjeta mt-3">
                     <h2 class="h6 text-uppercase text-secundario mb-3">
                       <i class="bi bi-person-plus"></i> Invitar jugador
                     </h2>
                     <form class="row g-2" data-form-invitar>
                       <div class="col-sm-8">
                         <input class="form-control" name="username" placeholder="Nombre de usuario exacto"
                                autocomplete="off" required>
                       </div>
                       <div class="col-sm-4">
                         <button class="btn btn-rojo w-100" type="submit">
                           <i class="bi bi-send"></i> Invitar
                         </button>
                       </div>
                     </form>
                     <p class="form-text mb-0 mt-2">El jugador recibe la invitación en su campanita y debe aceptarla.</p>
                   </div>`
                : ""
            }

            ${panelInvitaciones()}
            ${panelTorneos()}
          </div>

          <div class="col-lg-5">
            <div class="tarjeta">
              <h2 class="h5 mb-3"><i class="bi bi-trophy"></i> Torneos jugados</h2>
              ${
                equipo.inscripciones.length
                  ? `<div class="d-flex flex-column gap-2">
                       ${equipo.inscripciones
                         .map(
                           (inscripcion) => `
                         <a class="d-flex align-items-center justify-content-between gap-2 text-decoration-none pb-2 border-bottom"
                            href="#/torneos/${inscripcion.torneo.id}">
                           <div class="min-w-0">
                             <div class="enlace-jugador text-truncate">${escapar(inscripcion.torneo.nombre)}</div>
                             <div class="text-secundario small">
                               ${escapar(inscripcion.torneo.videojuego)} · ${fechaCorta(inscripcion.torneo.fecha)}
                             </div>
                           </div>
                           <span class="estado estado-${inscripcion.torneo.estado}">
                             ${escapar(ESTADOS[inscripcion.torneo.estado] || inscripcion.torneo.estado)}
                           </span>
                         </a>`
                         )
                         .join("")}
                     </div>`
                  : `<p class="text-secundario small mb-0">Todavía no inscribiste este equipo en un torneo.</p>`
              }
            </div>

            ${
              esMiembroActivo && !esCapitan
                ? `<div class="panel-accion mt-3">
                     <h2 class="h6 text-uppercase text-secundario mb-2">Tu membresía</h2>
                     <p class="text-secundario small">Podés salir del equipo cuando quieras, salvo que haya una inscripción activa.</p>
                     <button class="btn btn-outline-danger w-100" type="button" data-salir>
                       <i class="bi bi-box-arrow-right"></i> Salir del equipo
                     </button>
                   </div>`
                : ""
            }

            ${
              !estaAutenticado()
                ? `<div class="panel-accion mt-3">
                     <p class="text-secundario small mb-2">Iniciá sesión para postularte o gestionar tu equipo.</p>
                     <a class="btn btn-rojo w-100" href="#/login?redirect=${encodeURIComponent(`/equipos/${equipo.id}`)}">
                       Iniciar sesión
                     </a>
                   </div>`
                : ""
            }
          </div>
        </div>
      </div>`;

    const recargar = async (mensaje) => {
      await cargar();
      pintar();
      refrescarNotificaciones({ silencioso: true });
      toast(mensaje, { titulo: "Equipo", tipo: "equipo" });
    };

    const ejecutar = async (boton, accion, mensaje) => {
      if (boton) boton.disabled = true;
      try {
        await accion();
        await recargar(mensaje);
      } catch (error) {
        toast(resumenErrores(error).join(" · "), {
          titulo: "No se pudo completar",
          tipo: "disputa",
        });
        if (boton) boton.disabled = false;
      }
    };

    contenedor.querySelector("[data-form-invitar]")?.addEventListener("submit", (evento) => {
      evento.preventDefault();
      const formulario = evento.currentTarget;
      const username = new FormData(formulario).get("username");
      ejecutar(
        formulario.querySelector("button[type=submit]"),
        () => api.post(`/equipos/${equipo.id}/invitar`, { username: String(username || "").trim() }),
        "Invitación enviada."
      );
    });

    contenedor.querySelectorAll("[data-expulsar]").forEach((boton) => {
      boton.addEventListener("click", () => {
        if (!confirmar("¿Quitar a este jugador del equipo?", "Quitar")) return;
        ejecutar(
          boton,
          () => api.delete(`/equipos/${equipo.id}/miembros/${boton.dataset.expulsar}`),
          "Jugador quitado del equipo."
        );
      });
    });

    contenedor.querySelectorAll("[data-transferir]").forEach((boton) => {
      boton.addEventListener("click", () => {
        if (!confirmar("Este jugador pasará a ser el nuevo capitán del equipo.", "Transferir")) return;
        ejecutar(
          boton,
          () => api.post(`/equipos/${equipo.id}/capitan/${boton.dataset.transferir}`),
          "Capitanía transferida."
        );
      });
    });

    contenedor.querySelectorAll("[data-inscribir]").forEach((boton) => {
      boton.addEventListener("click", () => {
        ejecutar(
          boton,
          () =>
            api.post(`/torneos/${boton.dataset.inscribir}/inscribirse`, {
              equipo_id: equipo.id,
            }),
          "Equipo inscripto en el torneo."
        );
      });
    });

    contenedor.querySelector("[data-salir]")?.addEventListener("click", (evento) => {
      if (!confirmar("¿Salir de este equipo?", "Salir")) return;
      const boton = evento.currentTarget;
      boton.disabled = true;
      api
        .post(`/equipos/${equipo.id}/salir`)
        .then(() => {
          toast("Saliste del equipo.", { titulo: "Equipo", tipo: "equipo" });
          window.location.hash = "#/equipos";
        })
        .catch((error) => {
          toast(resumenErrores(error).join(" · "), { titulo: "No se pudo salir", tipo: "disputa" });
          boton.disabled = false;
        });
    });

    contenedor.querySelector("[data-eliminar]")?.addEventListener("click", (evento) => {
      if (!confirmar(`¿Eliminar «${equipo.nombre}»? Esta acción no se puede deshacer.`, "Eliminar")) return;
      const boton = evento.currentTarget;
      boton.disabled = true;
      api
        .delete(`/equipos/${equipo.id}`)
        .then(() => {
          toast("Equipo eliminado.", { titulo: "Equipo", tipo: "equipo" });
          window.location.hash = "#/equipos";
        })
        .catch((error) => {
          toast(resumenErrores(error).join(" · "), {
            titulo: "No se pudo eliminar",
            tipo: "disputa",
          });
          boton.disabled = false;
        });
    });
  }

  await cargar();
  pintar();
}
