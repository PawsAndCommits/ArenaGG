import { api } from "../api.js";
import { usuarioActual } from "../auth.js";
import { badgeEstadoTorneo, estadoVacio } from "../components.js";
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

export async function render(contenedor) {
  let estadisticas = null;
  let torneos = [];
  let usuarios = [];
  let inscripciones = [];

  async function cargar() {
    [estadisticas, torneos, usuarios, inscripciones] = await Promise.all([
      api.get("/estadisticas"),
      api.get("/torneos"),
      api.get("/usuarios"),
      api.get("/inscripciones"),
    ]);
  }

  function accionesTorneo(torneo) {
    return `
      <div class="d-flex flex-wrap gap-1">
        <a class="btn btn-sm btn-fantasma" href="#/torneos/${torneo.id}" title="Ver torneo">
          <i class="bi bi-eye"></i>
        </a>
        <a class="btn btn-sm btn-fantasma" href="#/torneos/${torneo.id}/editar" title="Editar torneo">
          <i class="bi bi-pencil-square"></i>
        </a>
        ${
          torneo.estado === "inscripciones_abiertas"
            ? `<button class="btn btn-sm btn-fantasma" type="button" title="Iniciar llave"
                       data-iniciar="${torneo.id}" ${torneo.inscriptos < 2 ? "disabled" : ""}>
                 <i class="bi bi-play-fill"></i>
               </button>`
            : ""
        }
        ${
          torneo.tiene_partidas
            ? `<button class="btn btn-sm btn-outline-warning" type="button" title="Reiniciar llave"
                       data-reiniciar="${torneo.id}">
                 <i class="bi bi-arrow-counterclockwise"></i>
               </button>`
            : ""
        }
        ${
          torneo.estado === "en_curso"
            ? `<button class="btn btn-sm btn-outline-warning" type="button" title="Finalizar torneo"
                       data-finalizar="${torneo.id}">
                 <i class="bi bi-flag-fill"></i>
               </button>`
            : ""
        }
        <button class="btn btn-sm btn-outline-danger" type="button" title="Eliminar torneo"
                data-eliminar-torneo="${torneo.id}">
          <i class="bi bi-trash"></i>
        </button>
      </div>`;
  }

  function filaUsuario(usuario) {
    const propio = usuarioActual()?.id === usuario.id;
    return `
      <tr>
        <td>
          <a class="enlace-jugador" href="#/usuarios/${usuario.id}">${escapar(usuario.username)}</a>
          ${propio ? '<span class="chip chip-sm ms-1">vos</span>' : ""}
        </td>
        <td class="text-secundario small">${escapar(usuario.email || "—")}</td>
        <td>
          <span class="chip chip-sm ${usuario.rol === "admin" ? "chip-rojo" : ""}">
            ${usuario.rol === "admin" ? "Administrador" : "Jugador"}
          </span>
        </td>
        <td class="text-secundario small">${fechaCorta(usuario.creado_en)}</td>
        <td>
          <div class="d-flex flex-wrap gap-1">
            ${
              propio
                ? ""
                : `<button class="btn btn-sm btn-fantasma" type="button"
                           data-rol="${usuario.id}/${usuario.rol === "admin" ? "jugador" : "admin"}">
                     <i class="bi bi-arrow-repeat"></i>
                     ${usuario.rol === "admin" ? "Quitar admin" : "Hacer admin"}
                   </button>
                   <button class="btn btn-sm btn-outline-danger" type="button"
                           data-eliminar-usuario="${usuario.id}">
                     <i class="bi bi-trash"></i>
                   </button>`
            }
          </div>
        </td>
      </tr>`;
  }

  function pintar() {
    const abiertos = estadisticas.torneos_por_estado?.inscripciones_abiertas || 0;
    const recientes = inscripciones.slice(0, 10);
    const nombreTorneo = (torneoId) =>
      torneos.find((torneo) => torneo.id === torneoId)?.nombre || `Torneo #${torneoId}`;
    contenedor.innerHTML = `
      <div class="container">
        <div class="cabecera-pagina d-flex flex-column flex-md-row justify-content-between align-items-md-end gap-3">
          <div>
            <h1><i class="bi bi-shield-lock"></i> Administración</h1>
            <p class="text-secundario mb-0">Gestión de torneos, jugadores e inscripciones.</p>
          </div>
          <a class="btn btn-rojo" href="#/torneos/nuevo">
            <i class="bi bi-plus-lg"></i> Nuevo torneo
          </a>
        </div>

        <div class="row g-3 mb-4">
          <div class="col-6 col-lg-3">
            <div class="tarjeta cifra">
              <i class="bi bi-people"></i>
              <div class="cifra-valor">${estadisticas.usuarios}</div>
              <div class="cifra-texto">Jugadores registrados</div>
            </div>
          </div>
          <div class="col-6 col-lg-3">
            <div class="tarjeta cifra">
              <i class="bi bi-trophy"></i>
              <div class="cifra-valor">${estadisticas.torneos}</div>
              <div class="cifra-texto">Torneos creados</div>
            </div>
          </div>
          <div class="col-6 col-lg-3">
            <div class="tarjeta cifra">
              <i class="bi bi-door-open"></i>
              <div class="cifra-valor">${abiertos}</div>
              <div class="cifra-texto">Con inscripciones abiertas</div>
            </div>
          </div>
          <div class="col-6 col-lg-3">
            <div class="tarjeta cifra">
              <i class="bi bi-card-checklist"></i>
              <div class="cifra-valor">${estadisticas.inscripciones}</div>
              <div class="cifra-texto">Inscripciones totales</div>
            </div>
          </div>
        </div>

        <section class="seccion">
          <div class="seccion-cabecera">
            <h2><i class="bi bi-trophy"></i> Torneos</h2>
            <a class="enlace-mas" href="#/torneos">Ver listado público <i class="bi bi-arrow-right"></i></a>
          </div>
          ${
            torneos.length
              ? `<div class="tarjeta overflow-hidden">
                   <div class="table-responsive">
                     <table class="table tabla-gamer align-middle">
                       <thead>
                         <tr>
                           <th>Torneo</th>
                           <th>Estado</th>
                           <th class="text-center">Inscriptos</th>
                           <th>Fecha</th>
                           <th class="text-end">Acciones</th>
                         </tr>
                       </thead>
                       <tbody>
                         ${torneos
                           .map(
                             (torneo) => `
                           <tr>
                             <td>
                               <a class="enlace-jugador" href="#/torneos/${torneo.id}">${escapar(torneo.nombre)}</a>
                               <div class="text-secundario small">
                                 ${escapar(torneo.videojuego)} · ${escapar(torneo.modalidad_texto)} ·
                                 ${escapar(torneo.formato_texto)}
                               </div>
                             </td>
                             <td>${badgeEstadoTorneo(torneo)}</td>
                             <td class="text-center">${torneo.inscriptos}/${torneo.cupo_maximo}</td>
                             <td class="text-secundario small">${fechaCorta(torneo.fecha)}</td>
                             <td class="text-end">${accionesTorneo(torneo)}</td>
                           </tr>`
                           )
                           .join("")}
                       </tbody>
                     </table>
                   </div>
                 </div>`
              : estadoVacio("trophy", "Todavía no hay torneos. Creá el primero.")
          }
        </section>

        <section class="seccion">
          <div class="seccion-cabecera">
            <h2><i class="bi bi-person-badge"></i> Usuarios</h2>
            <span class="text-secundario small">${usuarios.length} registrados</span>
          </div>
          <div class="tarjeta overflow-hidden">
            <div class="table-responsive">
              <table class="table tabla-gamer align-middle">
                <thead>
                  <tr>
                    <th>Usuario</th>
                    <th>Correo</th>
                    <th>Rol</th>
                    <th>Alta</th>
                    <th class="text-end">Acciones</th>
                  </tr>
                </thead>
                <tbody>${usuarios.map(filaUsuario).join("")}</tbody>
              </table>
            </div>
          </div>
        </section>

        <section class="seccion">
          <div class="seccion-cabecera">
            <h2><i class="bi bi-card-checklist"></i> Inscripciones recientes</h2>
            <span class="text-secundario small">${inscripciones.length} en total</span>
          </div>
          ${
            recientes.length
              ? `<div class="tarjeta overflow-hidden">
                   <div class="table-responsive">
                     <table class="table tabla-gamer align-middle">
                       <thead>
                         <tr>
                           <th>Participante</th>
                           <th>Torneo</th>
                           <th>Inscripto</th>
                           <th class="text-end">Acciones</th>
                         </tr>
                       </thead>
                       <tbody>
                         ${recientes
                           .map(
                             (inscripcion) => `
                           <tr>
                             <td>${escapar(inscripcion.nombre)}</td>
                             <td>
                               <a class="enlace-jugador" href="#/torneos/${inscripcion.torneo_id}">
                                 ${escapar(nombreTorneo(inscripcion.torneo_id))}
                               </a>
                             </td>
                             <td class="text-secundario small">${fechaCorta(inscripcion.inscripto_en)}</td>
                             <td class="text-end">
                               <button class="btn btn-sm btn-outline-danger" type="button"
                                       data-eliminar-inscripcion="${inscripcion.id}">
                                 <i class="bi bi-person-dash"></i> Quitar
                               </button>
                             </td>
                           </tr>`
                           )
                           .join("")}
                       </tbody>
                     </table>
                   </div>
                 </div>`
              : estadoVacio("card-checklist", "No hay inscripciones registradas.")
          }
        </section>
      </div>`;

    const ejecutar = async (boton, accion, mensaje) => {
      if (boton) boton.disabled = true;
      try {
        await accion();
        await cargar();
        pintar();
        refrescarNotificaciones({ silencioso: true });
        toast(mensaje, { titulo: "Administración", tipo: "resultado" });
      } catch (error) {
        toast(resumenErrores(error).join(" · "), {
          titulo: "No se pudo completar",
          tipo: "disputa",
        });
        if (boton) boton.disabled = false;
      }
    };

    contenedor.querySelectorAll("[data-iniciar]").forEach((boton) => {
      boton.addEventListener("click", () => {
        if (!confirmar("Se va a generar la llave y cerrar las inscripciones.", "Iniciar torneo")) return;
        ejecutar(
          boton,
          () => api.post(`/torneos/${boton.dataset.iniciar}/iniciar`),
          "Torneo iniciado."
        );
      });
    });

    contenedor.querySelectorAll("[data-reiniciar]").forEach((boton) => {
      boton.addEventListener("click", () => {
        if (!confirmar("Se borrarán las partidas y se reabrirán las inscripciones.", "Reiniciar llave")) return;
        ejecutar(
          boton,
          () => api.post(`/torneos/${boton.dataset.reiniciar}/reiniciar`),
          "Llave reiniciada."
        );
      });
    });

    contenedor.querySelectorAll("[data-finalizar]").forEach((boton) => {
      boton.addEventListener("click", () => {
        if (!confirmar("El torneo se marcará como finalizado.", "Finalizar torneo")) return;
        ejecutar(
          boton,
          () => api.post(`/torneos/${boton.dataset.finalizar}/finalizar`),
          "Torneo finalizado."
        );
      });
    });

    contenedor.querySelectorAll("[data-eliminar-torneo]").forEach((boton) => {
      boton.addEventListener("click", () => {
        if (!confirmar("¿Eliminar este torneo y todas sus inscripciones?", "Eliminar")) return;
        ejecutar(
          boton,
          () => api.delete(`/torneos/${boton.dataset.eliminarTorneo}`),
          "Torneo eliminado."
        );
      });
    });

    contenedor.querySelectorAll("[data-rol]").forEach((boton) => {
      boton.addEventListener("click", () => {
        const [usuarioId, rol] = boton.dataset.rol.split("/");
        ejecutar(
          boton,
          () => api.put(`/usuarios/${usuarioId}`, { rol }),
          `Rol actualizado a ${rol}.`
        );
      });
    });

    contenedor.querySelectorAll("[data-eliminar-usuario]").forEach((boton) => {
      boton.addEventListener("click", () => {
        if (!confirmar("¿Eliminar esta cuenta de usuario?", "Eliminar")) return;
        ejecutar(
          boton,
          () => api.delete(`/usuarios/${boton.dataset.eliminarUsuario}`),
          "Usuario eliminado."
        );
      });
    });

    contenedor.querySelectorAll("[data-eliminar-inscripcion]").forEach((boton) => {
      boton.addEventListener("click", () => {
        if (!confirmar("¿Quitar esta inscripción del torneo?", "Quitar")) return;
        ejecutar(
          boton,
          () => api.delete(`/inscripciones/${boton.dataset.eliminarInscripcion}`),
          "Inscripción eliminada."
        );
      });
    });
  }

  await cargar();
  pintar();
}
