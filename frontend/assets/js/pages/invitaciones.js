import { api } from "../api.js";
import { escudo, estadoVacio } from "../components.js";
import { refrescarNotificaciones, toast } from "../layout.js";
import {
  escapar,
  fechaCorta,
  resumenErrores,
} from "../utils.js";

export async function render(contenedor) {
  let invitaciones = [];

  async function cargar() {
    invitaciones = await api.get("/equipos/invitaciones");
  }

  function pintar() {
    contenedor.innerHTML = `
      <div class="container">
        <div class="cabecera-pagina d-flex flex-column flex-md-row justify-content-between align-items-md-end gap-3">
          <div>
            <h1><i class="bi bi-envelope-paper"></i> Invitaciones</h1>
            <p class="text-secundario mb-0">Equipos que quieren sumarte al roster.</p>
          </div>
          <a class="btn btn-fantasma" href="#/equipos">
            <i class="bi bi-people"></i> Mis equipos
          </a>
        </div>

        ${
          invitaciones.length
            ? `<div class="row g-3">
                 ${invitaciones
                   .map(
                     (invitacion) => `
                   <div class="col-md-6">
                     <div class="tarjeta h-100">
                       <div class="d-flex align-items-start gap-3">
                         ${escudo(invitacion.equipo.nombre, {
                           iniciales: invitacion.equipo.iniciales,
                           tamano: "escudo-lg",
                         })}
                         <div class="flex-grow-1 min-w-0">
                           <a class="enlace-jugador h4" href="#/equipos/${invitacion.equipo.id}">
                             ${escapar(invitacion.equipo.nombre)}
                           </a>
                           <div class="text-secundario small">
                             ${invitacion.equipo.tag ? `[${escapar(invitacion.equipo.tag)}] · ` : ""}
                             Capitán: ${escapar(invitacion.equipo.capitan || "—")}
                           </div>
                           <div class="meta mt-2">
                             <span><i class="bi bi-people"></i> ${invitacion.equipo.miembros} integrantes</span>
                             <span><i class="bi bi-clock"></i> ${fechaCorta(invitacion.creado_en)}</span>
                           </div>
                         </div>
                       </div>
                       ${
                         invitacion.equipo.descripcion
                           ? `<p class="text-secundario small mt-3 mb-0">${escapar(invitacion.equipo.descripcion)}</p>`
                           : ""
                       }
                       <p class="form-text mt-2 mb-3">
                         Invitación enviada por ${escapar(invitacion.invitado_por || "el capitán")}.
                       </p>
                       <div class="d-flex gap-2">
                         <button class="btn btn-rojo flex-grow-1" type="button"
                                 data-aceptar="${invitacion.equipo.id}/${invitacion.id}">
                           <i class="bi bi-check2"></i> Aceptar
                         </button>
                         <button class="btn btn-outline-danger flex-grow-1" type="button"
                                 data-rechazar="${invitacion.equipo.id}/${invitacion.id}">
                           <i class="bi bi-x-lg"></i> Rechazar
                         </button>
                       </div>
                     </div>
                   </div>`
                   )
                   .join("")}
               </div>`
            : estadoVacio("inbox", "No tenés invitaciones pendientes.")
        }
      </div>`;

    contenedor.querySelectorAll("[data-aceptar]").forEach((boton) => {
      boton.addEventListener("click", () => {
        const [equipoId, membresiaId] = boton.dataset.aceptar.split("/");
        responder(boton, equipoId, membresiaId, true);
      });
    });

    contenedor.querySelectorAll("[data-rechazar]").forEach((boton) => {
      boton.addEventListener("click", () => {
        const [equipoId, membresiaId] = boton.dataset.rechazar.split("/");
        responder(boton, equipoId, membresiaId, false);
      });
    });
  }

  async function responder(boton, equipoId, membresiaId, aceptar) {
    boton.disabled = true;
    try {
      await api.post(
        `/equipos/${equipoId}/invitaciones/${membresiaId}/${aceptar ? "aceptar" : "rechazar"}`
      );
      await cargar();
      pintar();
      refrescarNotificaciones({ silencioso: true });
      toast(aceptar ? "Te sumaste al equipo." : "Rechazaste la invitación.", {
        titulo: "Invitaciones",
        tipo: "equipo",
      });
    } catch (error) {
      toast(resumenErrores(error).join(" · "), {
        titulo: "No se pudo responder",
        tipo: "disputa",
      });
      boton.disabled = false;
    }
  }

  await cargar();
  pintar();
}
