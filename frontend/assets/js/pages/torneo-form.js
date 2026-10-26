import { api } from "../api.js";
import { esAdmin } from "../auth.js";
import { errorPagina } from "../components.js";
import { toast } from "../layout.js";
import {
  datosFormulario,
  escapar,
  fechaInput,
  inputAFecha,
  marcarErrores,
  resumenErrores,
} from "../utils.js";

const ESTADOS = [
  ["proximamente", "Próximamente"],
  ["inscripciones_abiertas", "Inscripciones abiertas"],
  ["en_curso", "En curso"],
  ["finalizado", "Finalizado"],
];

const ESTADOS_MANUALES = ESTADOS.slice(0, 2);

const FORMATOS = [
  ["BO1", "Mejor de 1"],
  ["BO3", "Mejor de 3"],
  ["BO5", "Mejor de 5"],
];

export async function render(contenedor, { params }) {
  const torneoId = params.id ? Number(params.id) : null;
  const torneo = torneoId ? await api.get(`/torneos/${torneoId}`) : null;
  const editando = Boolean(torneo);
  if (torneo && !torneo.puede_gestionar) {
    contenedor.innerHTML = errorPagina(
      "403",
      "Solo el organizador del torneo o un administrador puede editarlo."
    );
    return;
  }
  const estadoInicial = torneo?.estado || "inscripciones_abiertas";
  const estadoAutomatico = ["en_curso", "finalizado"].includes(estadoInicial);
  const modalidadInicial = torneo?.modalidad || "individual";
  const jugadoresInicial = torneo?.jugadores_por_equipo ?? 5;
  const puedeDestacar = esAdmin();

  contenedor.innerHTML = `
    <div class="container">
      <div class="row justify-content-center">
        <div class="col-lg-9">
          <a class="enlace-rojo small d-inline-block mb-3"
             href="#${editando ? `/torneos/${torneo.id}` : "/mis-torneos"}">
            <i class="bi bi-arrow-left"></i> ${editando ? "Volver al torneo" : "Volver a mis torneos"}
          </a>

          <div class="tarjeta tarjeta-form">
            <div class="mb-4">
              <h1 class="h3"><i class="bi bi-trophy"></i> ${editando ? "Editar torneo" : "Nuevo torneo"}</h1>
              <p class="text-secundario mb-0">
                ${editando
                  ? "Los cambios de modalidad, formato o estado tienen restricciones si el torneo ya tiene inscriptos o partidas."
                  : "Definí el formato y abrí las inscripciones cuando esté todo listo."}
              </p>
            </div>

            <div data-aviso></div>

            <form id="formTorneo" novalidate>
              <div class="row">
                <div class="col-md-8 mb-3">
                  <label class="form-label" for="nombre">Nombre <span class="text-danger">*</span></label>
                  <input class="form-control" id="nombre" name="nombre" required minlength="3" maxlength="100"
                         value="${escapar(torneo?.nombre || "")}" autofocus>
                </div>
                <div class="col-md-4 mb-3">
                  <label class="form-label" for="videojuego">Videojuego <span class="text-danger">*</span></label>
                  <input class="form-control" id="videojuego" name="videojuego" required minlength="2" maxlength="80"
                         value="${escapar(torneo?.videojuego || "")}" placeholder="Counter-Strike 1.6">
                </div>
              </div>

              <div class="mb-3">
                <label class="form-label" for="descripcion">Descripción</label>
                <textarea class="form-control" id="descripcion" name="descripcion" rows="2" maxlength="2000"
                          placeholder="De qué se trata el torneo">${escapar(torneo?.descripcion || "")}</textarea>
              </div>

              <div class="row">
                <div class="col-md-6 mb-3">
                  <label class="form-label" for="fecha">Fecha y hora <span class="text-danger">*</span></label>
                  <input class="form-control" type="datetime-local" id="fecha" name="fecha" required
                         value="${fechaInput(torneo?.fecha)}">
                </div>
                <div class="col-6 col-md-3 mb-3">
                  <label class="form-label" for="cupo_maximo">Cupo máximo <span class="text-danger">*</span></label>
                  <input class="form-control" type="number" id="cupo_maximo" name="cupo_maximo" required
                         min="2" max="128" value="${torneo?.cupo_maximo ?? 8}">
                </div>
                <div class="col-6 col-md-3 mb-3">
                  <label class="form-label" for="formato">Formato</label>
                  <select class="form-select" id="formato" name="formato"
                          ${torneo?.tiene_partidas ? "disabled" : ""}>
                    ${FORMATOS.map(
                      ([valor, texto]) =>
                        `<option value="${valor}" ${(torneo?.formato || "BO1") === valor ? "selected" : ""}>${texto}</option>`
                    ).join("")}
                  </select>
                  ${torneo?.tiene_partidas ? '<div class="form-text">No se puede cambiar con partidas generadas.</div>' : ""}
                </div>
              </div>

              <div class="row">
                <div class="col-md-4 mb-3">
                  <label class="form-label" for="modalidad">Modalidad</label>
                  <select class="form-select" id="modalidad" name="modalidad"
                          ${torneo?.inscriptos ? "disabled" : ""}>
                    <option value="individual" ${modalidadInicial === "individual" ? "selected" : ""}>Individual</option>
                    <option value="equipos" ${modalidadInicial === "equipos" ? "selected" : ""}>Por equipos</option>
                  </select>
                  ${torneo?.inscriptos ? '<div class="form-text">No se puede cambiar con inscriptos.</div>' : ""}
                </div>
                <div class="col-md-4 mb-3" data-campo-equipo>
                  <label class="form-label" for="jugadores_por_equipo">Jugadores por equipo</label>
                  <input class="form-control" type="number" id="jugadores_por_equipo" name="jugadores_por_equipo"
                         min="2" max="10" value="${jugadoresInicial}">
                </div>
                <div class="col-md-4 mb-3">
                  <label class="form-label" for="estado">Estado</label>
                  ${
                    estadoAutomatico
                      ? `<select class="form-select" id="estado" name="estado" disabled>
                           <option selected>${
                             ESTADOS.find(([valor]) => valor === estadoInicial)?.[1] ||
                             estadoInicial
                           }</option>
                         </select>
                         <div class="form-text">El estado lo actualiza el sistema al iniciar o finalizar el torneo.</div>`
                      : `<select class="form-select" id="estado" name="estado">
                           ${ESTADOS_MANUALES.map(
                             ([valor, texto]) =>
                               `<option value="${valor}" ${
                                 estadoInicial === valor ? "selected" : ""
                               }>${texto}</option>`
                           ).join("")}
                         </select>`
                  }
                </div>
              </div>

              <div class="row">
                <div class="col-md-8 mb-3">
                  <label class="form-label" for="premio">Premio</label>
                  <input class="form-control" id="premio" name="premio" maxlength="200"
                         value="${escapar(torneo?.premio || "")}" placeholder="Trofeo y premio en efectivo">
                </div>
                <div class="col-md-4 mb-3 d-flex align-items-end">
                  ${
                    puedeDestacar
                      ? `<div class="form-check form-switch mb-2">
                           <input class="form-check-input" type="checkbox" role="switch" id="destacado" name="destacado"
                                  ${torneo?.destacado ? "checked" : ""}>
                           <label class="form-check-label" for="destacado">Torneo destacado</label>
                         </div>`
                      : ""
                  }
                </div>
              </div>

              <div class="mb-3">
                <label class="form-label" for="reglas">Reglas</label>
                <textarea class="form-control" id="reglas" name="reglas" rows="5" maxlength="5000"
                          placeholder="Formato de mapas, puntualidad, conducta, etc.">${escapar(torneo?.reglas || "")}</textarea>
              </div>

              <div class="d-flex flex-wrap gap-2">
                <button class="btn btn-rojo" type="submit">
                  <i class="bi bi-check2"></i> ${editando ? "Guardar cambios" : "Crear torneo"}
                </button>
                <a class="btn btn-fantasma" href="#${editando ? `/torneos/${torneo.id}` : "/mis-torneos"}">Cancelar</a>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>`;

  const formulario = contenedor.querySelector("#formTorneo");
  const aviso = contenedor.querySelector("[data-aviso]");
  const modalidad = formulario.querySelector("#modalidad");
  const campoEquipo = formulario.querySelector("[data-campo-equipo]");
  const jugadores = formulario.querySelector("#jugadores_por_equipo");

  function ajustarModalidad() {
    const equipos = modalidad.value === "equipos";
    campoEquipo.classList.toggle("d-none", !equipos);
    jugadores.required = equipos;
  }
  modalidad.addEventListener("change", ajustarModalidad);
  ajustarModalidad();

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    aviso.innerHTML = "";
    marcarErrores(formulario, {});
    const boton = formulario.querySelector("button[type=submit]");
    const crudos = datosFormulario(formulario);
    const porEquipos = modalidad.value === "equipos";

    const cuerpo = {
      nombre: crudos.nombre,
      descripcion: crudos.descripcion,
      videojuego: crudos.videojuego,
      fecha: inputAFecha(crudos.fecha),
      cupo_maximo: crudos.cupo_maximo,
      estado: crudos.estado,
      modalidad: modalidad.value,
      jugadores_por_equipo: porEquipos
        ? jugadores.value === ""
          ? null
          : Number(jugadores.value)
        : null,
      ...(puedeDestacar ? { destacado: Boolean(crudos.destacado) } : {}),
      formato: formulario.querySelector("#formato").value,
      premio: crudos.premio,
      reglas: crudos.reglas,
    };

    boton.disabled = true;
    try {
      if (editando) {
        await api.put(`/torneos/${torneo.id}`, cuerpo);
        toast("Torneo actualizado.", { titulo: "Torneo", tipo: "torneo" });
        window.location.hash = `#/torneos/${torneo.id}`;
      } else {
        const creado = await api.post("/torneos", cuerpo);
        toast("Torneo creado.", { titulo: "Torneo", tipo: "torneo" });
        window.location.hash = `#/torneos/${creado.id}`;
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
