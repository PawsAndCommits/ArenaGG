import { api } from "../api.js";
import { esAdmin } from "../auth.js";
import { toast } from "../layout.js";
import {
  datosFormulario,
  escapar,
  marcarErrores,
  resumenErrores,
} from "../utils.js";

export async function render(contenedor, { params }) {
  const equipoId = params.id ? Number(params.id) : null;
  let equipo = null;

  if (equipoId) {
    equipo = await api.get(`/equipos/${equipoId}`);
    if (equipo.mi_rol !== "capitan" && !esAdmin()) {
      const error = new Error("Solo el capitán puede editar este equipo.");
      error.status = 403;
      throw error;
    }
  }

  const editando = Boolean(equipo);

  contenedor.innerHTML = `
    <div class="container">
      <div class="row justify-content-center">
        <div class="col-lg-7">
          <a class="enlace-rojo small d-inline-block mb-3"
             href="#${editando ? `/equipos/${equipo.id}` : "/equipos"}">
            <i class="bi bi-arrow-left"></i> ${editando ? "Volver al equipo" : "Volver a equipos"}
          </a>

          <div class="tarjeta tarjeta-form">
            <div class="mb-4">
              <h1 class="h3"><i class="bi bi-shield-shaded"></i> ${editando ? "Editar equipo" : "Crear equipo"}</h1>
              <p class="text-secundario mb-0">
                ${editando
                  ? "Actualizá el nombre, el tag o la presentación del equipo."
                  : "Vas a quedar como capitán y podrás invitar al resto del roster."}
              </p>
            </div>

            <div data-aviso></div>

            <form id="formEquipo" novalidate>
              <div class="mb-3">
                <label class="form-label" for="nombre">Nombre del equipo <span class="text-danger">*</span></label>
                <input class="form-control" id="nombre" name="nombre" required minlength="2" maxlength="60"
                       value="${escapar(equipo?.nombre || "")}" autofocus>
                <div class="form-text">Entre 2 y 60 caracteres. No puede repetirse.</div>
              </div>
              <div class="row">
                <div class="col-sm-4 mb-3">
                  <label class="form-label" for="tag">Tag</label>
                  <input class="form-control text-uppercase" id="tag" name="tag" maxlength="10"
                         value="${escapar(equipo?.tag || "")}" placeholder="AG">
                  <div class="form-text">Hasta 10 caracteres.</div>
                </div>
                <div class="col-sm-8 mb-3">
                  <label class="form-label" for="descripcion">Descripción</label>
                  <textarea class="form-control" id="descripcion" name="descripcion" rows="2" maxlength="500"
                            placeholder="Una breve presentación del equipo">${escapar(equipo?.descripcion || "")}</textarea>
                </div>
              </div>
              <div class="d-flex flex-wrap gap-2">
                <button class="btn btn-rojo" type="submit">
                  <i class="bi bi-check2"></i> ${editando ? "Guardar cambios" : "Crear equipo"}
                </button>
                <a class="btn btn-fantasma" href="#${editando ? `/equipos/${equipo.id}` : "/equipos"}">Cancelar</a>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>`;

  const formulario = contenedor.querySelector("#formEquipo");
  const aviso = contenedor.querySelector("[data-aviso]");

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    aviso.innerHTML = "";
    marcarErrores(formulario, {});
    const boton = formulario.querySelector("button[type=submit]");
    const datos = datosFormulario(formulario);
    boton.disabled = true;

    try {
      if (editando) {
        await api.put(`/equipos/${equipo.id}`, datos);
        toast("Equipo actualizado.", { titulo: "Equipo", tipo: "equipo" });
        window.location.hash = `#/equipos/${equipo.id}`;
      } else {
        const creado = await api.post("/equipos", datos);
        toast("Equipo creado. Ahora armá el roster.", {
          titulo: "Equipo listo",
          tipo: "equipo",
        });
        window.location.hash = `#/equipos/${creado.id}`;
      }
    } catch (error) {
      marcarErrores(formulario, error.errores || {});
      aviso.innerHTML = `<div class="alert alert-danger">${resumenErrores(error)
        .map((mensaje) => `<div>${escapar(mensaje)}</div>`)
        .join("")}</div>`;
      boton.disabled = false;
    }
  });
}
