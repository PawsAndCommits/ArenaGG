import { api } from "../api.js";
import { tarjetaTorneo } from "../components.js";

export async function render(contenedor) {
  const torneos = await api.get("/torneos/mios");

  contenedor.innerHTML = `
    <div class="container">
      <div class="cabecera-pagina d-flex flex-column flex-md-row justify-content-between align-items-md-end gap-3">
        <div>
          <h1><i class="bi bi-trophy"></i> Mis torneos</h1>
          <p class="text-secundario mb-0">Los torneos que organizás y podés gestionar.</p>
        </div>
        <a class="btn btn-rojo" href="#/torneos/nuevo">
          <i class="bi bi-plus-lg"></i> Nuevo torneo
        </a>
      </div>

      ${
        torneos.length
          ? `<div class="row g-4">${torneos
              .map(
                (torneo) => `
                <div class="col-md-6 col-lg-4">
                  <div class="d-flex flex-column h-100">
                    ${tarjetaTorneo(torneo)}
                    <div class="d-flex gap-2 mt-2">
                      <a class="btn btn-sm btn-fantasma flex-grow-1" href="#/torneos/${torneo.id}/editar">
                        <i class="bi bi-pencil-square"></i> Editar
                      </a>
                      <a class="btn btn-sm btn-fantasma flex-grow-1" href="#/torneos/${torneo.id}">
                        <i class="bi bi-eye"></i> Ver
                      </a>
                    </div>
                  </div>
                </div>`
              )
              .join("")}</div>`
          : `<div class="tarjeta p-5 text-center">
               <i class="bi bi-trophy display-6 text-rojo"></i>
               <h2 class="h4 mt-3">Todavía no organizás torneos</h2>
               <p class="text-secundario">Creá el primero y abrí las inscripciones cuando esté listo.</p>
               <a class="btn btn-rojo" href="#/torneos/nuevo">
                 <i class="bi bi-plus-lg"></i> Crear torneo
               </a>
             </div>`
      }
    </div>`;
}
