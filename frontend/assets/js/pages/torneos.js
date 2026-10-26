import { api } from "../api.js";
import { estaAutenticado } from "../auth.js";
import { tarjetaTorneo, estadoVacio } from "../components.js";
import { escapar } from "../utils.js";

const ESTADOS = [
  ["inscripciones_abiertas", "Inscripciones abiertas"],
  ["proximamente", "Próximamente"],
  ["en_curso", "En curso"],
  ["finalizado", "Finalizado"],
];

const MODALIDADES = [
  ["individual", "Individual"],
  ["equipos", "Por equipos"],
];

export async function render(contenedor, { query }) {
  const filtros = {
    q: query.get("q") || "",
    estado: query.get("estado") || "",
    modalidad: query.get("modalidad") || "",
    videojuego: query.get("videojuego") || "",
  };

  const [torneos, videojuegos] = await Promise.all([
    api.get("/torneos", filtros),
    api.get("/videojuegos"),
  ]);

  contenedor.innerHTML = `
    <div class="container">
      <div class="cabecera-pagina d-flex flex-column flex-md-row justify-content-between align-items-md-end gap-3">
        <div>
          <h1><i class="bi bi-trophy"></i> Torneos</h1>
          <p class="text-secundario mb-0">Encontrá tu próximo desafío.</p>
        </div>
        ${
          estaAutenticado()
            ? '<a href="#/torneos/nuevo" class="btn btn-rojo"><i class="bi bi-plus-lg"></i> Nuevo torneo</a>'
            : ""
        }
      </div>

      <form class="tarjeta filtros mb-4" id="filtrosTorneos">
        <div class="row g-2 align-items-end">
          <div class="col-md-4">
            <label class="form-label small" for="q">Buscar</label>
            <div class="input-group">
              <span class="input-group-text"><i class="bi bi-search"></i></span>
              <input class="form-control" id="q" name="q" value="${escapar(
                filtros.q
              )}" placeholder="Nombre o descripción">
            </div>
          </div>
          <div class="col-6 col-md-2">
            <label class="form-label small" for="estado">Estado</label>
            <select class="form-select" id="estado" name="estado">
              <option value="">Todos</option>
              ${ESTADOS.map(
                ([valor, texto]) =>
                  `<option value="${valor}" ${
                    filtros.estado === valor ? "selected" : ""
                  }>${texto}</option>`
              ).join("")}
            </select>
          </div>
          <div class="col-6 col-md-2">
            <label class="form-label small" for="modalidad">Modalidad</label>
            <select class="form-select" id="modalidad" name="modalidad">
              <option value="">Todas</option>
              ${MODALIDADES.map(
                ([valor, texto]) =>
                  `<option value="${valor}" ${
                    filtros.modalidad === valor ? "selected" : ""
                  }>${texto}</option>`
              ).join("")}
            </select>
          </div>
          <div class="col-6 col-md-2">
            <label class="form-label small" for="videojuego">Juego</label>
            <select class="form-select" id="videojuego" name="videojuego">
              <option value="">Todos</option>
              ${videojuegos
                .map(
                  (juego) =>
                    `<option value="${escapar(juego)}" ${
                      filtros.videojuego === juego ? "selected" : ""
                    }>${escapar(juego)}</option>`
                )
                .join("")}
            </select>
          </div>
          <div class="col-6 col-md-2 d-flex gap-2">
            <button class="btn btn-rojo flex-grow-1" type="submit"><i class="bi bi-funnel"></i> Filtrar</button>
            <a class="btn btn-fantasma" href="#/torneos" title="Limpiar filtros"><i class="bi bi-x-lg"></i></a>
          </div>
        </div>
      </form>

      <div class="d-flex justify-content-between align-items-center mb-3">
        <span class="text-secundario small">${torneos.length} torneo${
          torneos.length === 1 ? "" : "s"
        } encontrado${torneos.length === 1 ? "" : "s"}</span>
      </div>

      ${
        torneos.length
          ? `<div class="row g-3">${torneos
              .map((torneo) => `<div class="col-md-6 col-lg-4">${tarjetaTorneo(torneo)}</div>`)
              .join("")}</div>`
          : estadoVacio("search", "No encontramos torneos con esos filtros.")
      }
    </div>`;

  contenedor.querySelector("#filtrosTorneos")?.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const datos = new FormData(evento.currentTarget);
    const parametros = new URLSearchParams();
    datos.forEach((valor, clave) => {
      if (String(valor).trim()) parametros.append(clave, String(valor).trim());
    });
    window.location.hash = `#/torneos${parametros.toString() ? `?${parametros}` : ""}`;
  });
}
