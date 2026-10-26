import { api } from "../api.js";
import { estaAutenticado } from "../auth.js";
import { tarjetaTorneo, estadoVacio } from "../components.js";
import { escapar } from "../utils.js";

export async function render(contenedor) {
  const [estadisticas, torneos] = await Promise.all([
    api.get("/estadisticas"),
    api.get("/torneos"),
  ]);

  const abiertos = torneos.filter((torneo) => torneo.estado === "inscripciones_abiertas").slice(0, 6);
  const destacados = torneos
    .filter((torneo) => torneo.destacado && !abiertos.some((abierto) => abierto.id === torneo.id))
    .slice(0, 3);
  const cifras = [
    ["trophy", estadisticas.torneos, "Torneos"],
    ["people", estadisticas.usuarios, "Jugadores"],
    ["door-open", estadisticas.torneos_por_estado?.inscripciones_abiertas ?? 0, "Inscripciones abiertas"],
    ["card-checklist", estadisticas.inscripciones, "Participaciones"],
  ];

  contenedor.innerHTML = `
    <section class="hero">
      <div class="container">
        <div class="row align-items-center g-4">
          <div class="col-lg-7">
            <span class="chip mb-3"><i class="bi bi-broadcast"></i> Torneos, equipos y resultados en un solo lugar</span>
            <h1 class="hero-titulo">Jugá en serio.<br><span class="text-gradiente">Ganá en arena.</span></h1>
            <p class="hero-texto">Creá tu equipo, armá el roster y competí en torneos individuales o por equipos. Resultados confirmados por los capitanes y llaves que se actualizan solas.</p>
            <div class="d-flex flex-wrap gap-2 mt-4">
              <a href="#/torneos?estado=inscripciones_abiertas" class="btn btn-lg btn-rojo">
                <i class="bi bi-door-open"></i> Ver inscripciones abiertas
              </a>
              ${
                estaAutenticado()
                  ? '<a href="#/equipos" class="btn btn-lg btn-fantasma"><i class="bi bi-people"></i> Mis equipos</a>'
                  : '<a href="#/registro" class="btn btn-lg btn-fantasma"><i class="bi bi-person-plus"></i> Crear cuenta</a>'
              }
            </div>
          </div>
          <div class="col-lg-5">
            <div class="hero-panel">
              <div class="row g-3">
                ${cifras
                  .map(
                    ([icono, valor, texto]) => `
                  <div class="col-6">
                    <div class="cifra">
                      <i class="bi bi-${icono}"></i>
                      <div class="cifra-valor">${Number(valor) || 0}</div>
                      <div class="cifra-texto">${escapar(texto)}</div>
                    </div>
                  </div>`
                  )
                  .join("")}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div class="container">
      <section class="seccion">
        <div class="seccion-cabecera">
          <h2><i class="bi bi-door-open"></i> Inscripciones abiertas</h2>
          <a href="#/torneos?estado=inscripciones_abiertas" class="enlace-mas">Ver todos <i class="bi bi-arrow-right"></i></a>
        </div>
        ${
          abiertos.length
            ? `<div class="row g-3">${abiertos
                .map((torneo) => `<div class="col-md-6 col-lg-4">${tarjetaTorneo(torneo)}</div>`)
                .join("")}</div>`
            : estadoVacio("inbox", "No hay torneos con inscripciones abiertas en este momento.")
        }
      </section>

      ${
        destacados.length
          ? `
        <section class="seccion">
          <div class="seccion-cabecera">
            <h2><i class="bi bi-star-fill"></i> Torneos destacados</h2>
          </div>
          <div class="row g-3">
            ${destacados
              .map(
                (torneo) =>
                  `<div class="col-md-6 col-lg-4">${tarjetaTorneo(torneo, { destacada: true })}</div>`
              )
              .join("")}
          </div>
        </section>`
          : ""
      }

      <section class="seccion">
        <div class="seccion-cabecera">
          <h2><i class="bi bi-lightning-charge"></i> Cómo funciona</h2>
        </div>
        <div class="row g-3">
          <div class="col-md-4">
            <div class="tarjeta h-100">
              <span class="marca-icono mb-3"><i class="bi bi-person-plus"></i></span>
              <h3 class="h5">1. Creá tu cuenta</h3>
              <p class="text-secundario small mb-0">Registrate, elegí tus juegos y armá tu equipo con invitaciones.</p>
            </div>
          </div>
          <div class="col-md-4">
            <div class="tarjeta h-100">
              <span class="marca-icono mb-3"><i class="bi bi-clipboard-check"></i></span>
              <h3 class="h5">2. Inscribite</h3>
              <p class="text-secundario small mb-0">Elegí un torneo individual o por equipos, confirmá el roster y quedate con tu lugar.</p>
            </div>
          </div>
          <div class="col-md-4">
            <div class="tarjeta h-100">
              <span class="marca-icono mb-3"><i class="bi bi-trophy"></i></span>
              <h3 class="h5">3. Jugá y confirmá</h3>
              <p class="text-secundario small mb-0">La sala te avisa cuando tu partida está lista. Cargá el marcador y el rival lo confirma.</p>
            </div>
          </div>
        </div>
      </section>
    </div>`;
}
