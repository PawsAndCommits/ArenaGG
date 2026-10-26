import { api } from "../api.js";
import { estaAutenticado } from "../auth.js";
import { escudo, estadoVacio } from "../components.js";
import { escapar } from "../utils.js";

const ETIQUETAS_ROL = {
  capitan: "Capitán",
  jugador: "Miembro",
  invitado: "Invitado",
  rechazado: "Invitación rechazada",
};

function tarjetaEquipo(equipo) {
  const rol = ETIQUETAS_ROL[equipo.mi_rol];
  return `
    <a class="tarjeta equipo-mini h-100" href="#/equipos/${equipo.id}"
       data-equipo="${escapar(`${equipo.nombre} ${equipo.tag} ${equipo.capitan || ""}`.toLowerCase())}">
      ${escudo(equipo.nombre, { iniciales: equipo.iniciales })}
      <div class="flex-grow-1 min-w-0">
        <div class="equipo-mini-nombre text-truncate">${escapar(equipo.nombre)}</div>
        <div class="text-secundario small text-truncate">
          ${equipo.tag ? `[${escapar(equipo.tag)}] · ` : ""}Capitán: ${escapar(equipo.capitan || "—")}
        </div>
        ${
          equipo.descripcion
            ? `<div class="text-secundario small recorte-2 mt-1">${escapar(equipo.descripcion)}</div>`
            : ""
        }
      </div>
      <div class="text-end flex-shrink-0">
        <div class="fw-semibold">${equipo.miembros}</div>
        <div class="text-secundario small">jugador${equipo.miembros === 1 ? "" : "es"}</div>
        ${rol ? `<span class="chip chip-sm mt-1">${escapar(rol)}</span>` : ""}
      </div>
    </a>`;
}

export async function render(contenedor) {
  const autenticado = estaAutenticado();
  const [equipos, mios, invitaciones] = await Promise.all([
    api.get("/equipos"),
    autenticado ? api.get("/equipos/mios") : Promise.resolve([]),
    autenticado ? api.get("/equipos/invitaciones") : Promise.resolve([]),
  ]);

  contenedor.innerHTML = `
    <div class="container">
      <div class="cabecera-pagina d-flex flex-column flex-md-row justify-content-between align-items-md-end gap-3">
        <div>
          <h1><i class="bi bi-people"></i> Equipos</h1>
          <p class="text-secundario mb-0">Armá el roster y competí por equipos.</p>
        </div>
        ${
          autenticado
            ? `<div class="d-flex flex-wrap gap-2">
                 <a class="btn btn-fantasma" href="#/equipos/invitaciones">
                   <i class="bi bi-envelope"></i> Invitaciones
                   ${invitaciones.length ? `<span class="badge text-bg-rojo ms-1">${invitaciones.length}</span>` : ""}
                 </a>
                 <a class="btn btn-rojo" href="#/equipos/nuevo"><i class="bi bi-plus-lg"></i> Crear equipo</a>
               </div>`
            : `<a class="btn btn-rojo" href="#/login?redirect=${encodeURIComponent("/equipos/nuevo")}">
                 <i class="bi bi-box-arrow-in-right"></i> Iniciar sesión para crear
               </a>`
        }
      </div>

      ${
        invitaciones.length
          ? `<a class="tarjeta panel-accion d-flex align-items-center gap-3 mb-4 text-decoration-none"
                href="#/equipos/invitaciones">
               <span class="marca-icono"><i class="bi bi-envelope-paper"></i></span>
               <div class="flex-grow-1">
                 <strong>Tenés ${invitaciones.length} invitación${invitaciones.length === 1 ? "" : "es"} pendiente${invitaciones.length === 1 ? "" : "s"}.</strong>
                 <div class="text-secundario small">Revisá los equipos que te quieren sumar al roster.</div>
               </div>
               <i class="bi bi-arrow-right text-rojo"></i>
             </a>`
          : ""
      }

      ${
        autenticado
          ? `<section class="seccion">
               <div class="seccion-cabecera">
                 <h2><i class="bi bi-star"></i> Mis equipos</h2>
                 <a class="enlace-mas" href="#/equipos/nuevo">Crear otro <i class="bi bi-plus-lg"></i></a>
               </div>
               ${
                 mios.length
                   ? `<div class="equipo-grid">${mios.map(tarjetaEquipo).join("")}</div>`
                   : estadoVacio("shield", "Todavía no pertenecés a ningún equipo.")
               }
             </section>`
          : ""
      }

      <section class="seccion">
        <div class="seccion-cabecera">
          <h2><i class="bi bi-shield-shaded"></i> Todos los equipos</h2>
          <span class="text-secundario small" data-contador>${equipos.length} equipo${equipos.length === 1 ? "" : "s"}</span>
        </div>
        <div class="tarjeta filtros mb-3">
          <label class="form-label small" for="buscarEquipos">Buscar equipo</label>
          <div class="input-group">
            <span class="input-group-text"><i class="bi bi-search"></i></span>
            <input class="form-control" id="buscarEquipos" placeholder="Nombre, tag o capitán" autocomplete="off">
          </div>
        </div>
        ${
          equipos.length
            ? `<div class="equipo-grid" data-lista-equipos>${equipos.map(tarjetaEquipo).join("")}</div>
               <div class="vacio d-none mt-3" data-sin-resultados>
                 <i class="bi bi-search"></i>
                 <p class="mb-0">No encontramos equipos con esa búsqueda.</p>
               </div>`
            : estadoVacio("shield", "Todavía no se creó ningún equipo.")
        }
      </section>
    </div>`;

  const buscador = contenedor.querySelector("#buscarEquipos");
  const lista = contenedor.querySelector("[data-lista-equipos]");
  if (!buscador || !lista) return;

  const contador = contenedor.querySelector("[data-contador]");
  const vacio = contenedor.querySelector("[data-sin-resultados]");

  buscador.addEventListener("input", () => {
    const termino = buscador.value.trim().toLowerCase();
    let visibles = 0;
    lista.querySelectorAll("[data-equipo]").forEach((tarjeta) => {
      const coincide = !termino || tarjeta.dataset.equipo.includes(termino);
      tarjeta.classList.toggle("d-none", !coincide);
      if (coincide) visibles += 1;
    });
    vacio?.classList.toggle("d-none", visibles > 0);
    if (contador) {
      contador.textContent = `${visibles} de ${equipos.length} equipos`;
    }
  });
}
