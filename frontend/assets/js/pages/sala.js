import { api } from "../api.js";
import { esAdmin } from "../auth.js";
import {
  badgeEstadoPartida,
  insignia,
} from "../components.js";
import { refrescarNotificaciones, toast } from "../layout.js";
import {
  confirmar,
  escapar,
  fechaHora,
  fechaInput,
  mensajeError,
  resumenErrores,
} from "../utils.js";

const OBJETIVOS = { BO1: 1, BO3: 2, BO5: 3 };

function lado(participante, puntaje, ganador, alineacion = "start") {
  const roster = (participante?.roster || [])
    .map((jugador) => escapar(jugador.username))
    .join(" · ");
  return `
    <div class="sala-lado ${ganador ? "ganador" : ""}">
      ${insignia(participante, "escudo-lg")}
      <div class="sala-lado-nombre text-${alineacion}">${escapar(
        participante?.nombre || "Por definir"
      )}</div>
      ${roster ? `<div class="sala-lado-roster">${roster}</div>` : ""}
    </div>`;
}

function cajaResultado(partida, torneo) {
  const resultado = partida.resultado;
  const objetivo = OBJETIVOS[torneo.formato] || 1;

  if (resultado) {
    const estadoClases = {
      confirmado: "confirmado",
      pendiente: "pendiente",
      disputa: "disputa",
    };
    const titulos = {
      confirmado: "Resultado confirmado",
      pendiente: "Esperando confirmación",
      disputa: "Resultado en disputa",
    };
    return `
      <div class="resultado-caja ${estadoClases[resultado.estado] || ""}">
        <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
          <h2 class="h5 mb-0"><i class="bi bi-clipboard-check"></i> ${titulos[resultado.estado] || "Resultado"}</h2>
          <span class="marcador">${resultado.puntaje1} - ${resultado.puntaje2}</span>
        </div>
        <div class="meta mt-2">
          ${resultado.registrado_por ? `<span><i class="bi bi-person"></i> Cargó ${escapar(resultado.registrado_por)}</span>` : ""}
          ${resultado.confirmado_por ? `<span><i class="bi bi-check2"></i> Confirmó ${escapar(resultado.confirmado_por)}</span>` : ""}
          ${resultado.registrado_en ? `<span><i class="bi bi-clock"></i> ${fechaHora(resultado.registrado_en)}</span>` : ""}
        </div>
        ${
          resultado.disputa_motivo
            ? `<div class="alert alert-warning mt-3 mb-0"><strong>Motivo:</strong> ${escapar(
                resultado.disputa_motivo
              )}</div>`
            : ""
        }
      </div>`;
  }

  return `
    <div class="resultado-caja">
      <h2 class="h5"><i class="bi bi-hourglass-split"></i> Resultado pendiente</h2>
      <p class="text-secundario small mb-0">${
        partida.lista_para_jugar
          ? `Al mejor de ${objetivo * 2 - 1}. El ganador debe llegar a ${objetivo} mapas.`
          : "La partida todavía no está completa."
      }</p>
    </div>`;
}

function formularioReportar(partida, torneo) {
  const objetivo = OBJETIVOS[torneo.formato] || 1;
  const opciones = (seleccionado) =>
    Array.from({ length: objetivo + 1 }, (_, indice) => indice)
      .map(
        (valor) =>
          `<option value="${valor}" ${valor === seleccionado ? "selected" : ""}>${valor}</option>`
      )
      .join("");

  return `
    <form class="resultado-caja mt-3" data-form-resultado>
      <h2 class="h5 mb-3"><i class="bi bi-pencil-square"></i> Cargar marcador</h2>
      <div class="row g-2 align-items-end">
        <div class="col-5">
          <label class="form-label small">${escapar(partida.participante1?.nombre || "Participante 1")}</label>
          <select class="form-select" name="puntaje1">${opciones(objetivo)}</select>
        </div>
        <div class="col-2 text-center pb-2 marcador">-</div>
        <div class="col-5">
          <label class="form-label small">${escapar(partida.participante2?.nombre || "Participante 2")}</label>
          <select class="form-select" name="puntaje2">${opciones(0)}</select>
        </div>
      </div>
      <p class="form-text">Para ${torneo.formato} el ganador debe llegar a ${objetivo} mapas y el perdedor no puede llegar a ${objetivo}.</p>
      <button class="btn btn-rojo w-100" type="submit"><i class="bi bi-send"></i> Enviar resultado</button>
    </form>`;
}

function accionesResultado(partida, torneo) {
  const objetivo = OBJETIVOS[torneo.formato] || 1;
  const resultado = partida.resultado;
  const opciones = (seleccionado) =>
    Array.from({ length: objetivo + 1 }, (_, indice) => indice)
      .map(
        (valor) =>
          `<option value="${valor}" ${valor === seleccionado ? "selected" : ""}>${valor}</option>`
      )
      .join("");

  const bloques = [];

  if (partida.puede_reportar) {
    bloques.push(formularioReportar(partida, torneo));
  }

  if (partida.puede_confirmar) {
    bloques.push(`
      <div class="resultado-caja pendiente mt-3">
        <h2 class="h5"><i class="bi bi-check2-circle"></i> Confirmá el resultado</h2>
        <p class="text-secundario small">Si el marcador es correcto, confirmalo. Si no, abrí una disputa.</p>
        <div class="d-flex flex-wrap gap-2">
          <button class="btn btn-rojo" type="button" data-confirmar>
            <i class="bi bi-check2"></i> Confirmar resultado
          </button>
          <button class="btn btn-fantasma" type="button" data-abrir-disputa>
            <i class="bi bi-exclamation-triangle"></i> Disputar
          </button>
        </div>
        <form class="mt-3 d-none" data-form-disputa>
          <label class="form-label small" for="motivoDisputa">Motivo de la disputa</label>
          <textarea class="form-control mb-2" id="motivoDisputa" name="motivo" rows="3" maxlength="255"
                    placeholder="Contá qué pasó con el marcador (mínimo 3 caracteres)"></textarea>
          <button class="btn btn-outline-warning" type="submit">Enviar disputa</button>
        </form>
      </div>`);
  }

  if (partida.puede_resolver) {
    bloques.push(`
      <form class="resultado-caja disputa mt-3" data-form-resolver>
        <h2 class="h5 mb-3"><i class="bi bi-shield-lock"></i> Resolver como administrador</h2>
        <div class="row g-2 align-items-end">
          <div class="col-5">
            <label class="form-label small">${escapar(partida.participante1?.nombre || "Participante 1")}</label>
            <select class="form-select" name="puntaje1">${opciones(resultado?.puntaje1 ?? objetivo)}</select>
          </div>
          <div class="col-2 text-center pb-2 marcador">-</div>
          <div class="col-5">
            <label class="form-label small">${escapar(partida.participante2?.nombre || "Participante 2")}</label>
            <select class="form-select" name="puntaje2">${opciones(resultado?.puntaje2 ?? 0)}</select>
          </div>
        </div>
        <div class="d-flex flex-wrap gap-2 mt-3">
          <button class="btn btn-rojo" type="submit"><i class="bi bi-check2-all"></i> Confirmar marcador</button>
          <button class="btn btn-outline-danger" type="button" data-rechazar>
            <i class="bi bi-arrow-counterclockwise"></i> Rechazar resultado
          </button>
        </div>
      </form>`);
  }

  if (esAdmin()) {
    bloques.push(`
      <form class="resultado-caja mt-3" data-form-programar>
        <h2 class="h5 mb-3"><i class="bi bi-clock"></i> Programar partida</h2>
        <div class="row g-2 align-items-end">
          <div class="col-sm-8">
            <label class="form-label small" for="fechaProgramada">Fecha y hora</label>
            <input class="form-control" type="datetime-local" id="fechaProgramada" name="fecha_programada"
                   value="${fechaInput(partida.fecha_programada)}" required>
          </div>
          <div class="col-sm-4">
            <button class="btn btn-fantasma w-100" type="submit"><i class="bi bi-calendar-check"></i> Guardar</button>
          </div>
        </div>
      </form>`);
  }

  return bloques.join("");
}

export async function render(contenedor, { params }) {
  const { id: torneoId, partidaId } = params;

  async function cargar() {
    const [partida, torneo] = await Promise.all([
      api.get(`/torneos/${torneoId}/partidas/${partidaId}`),
      api.get(`/torneos/${torneoId}`),
    ]);
    return { partida, torneo };
  }

  function pintar({ partida, torneo }) {
    const resultado = partida.resultado;
    const gano1 = partida.ganador && partida.participante1 &&
      partida.ganador.inscripcion_id === partida.participante1.inscripcion_id;
    const gano2 = partida.ganador && partida.participante2 &&
      partida.ganador.inscripcion_id === partida.participante2.inscripcion_id;
    const score1 = resultado ? resultado.puntaje1 : "–";
    const score2 = resultado ? resultado.puntaje2 : "–";

    contenedor.innerHTML = `
      <div class="container">
        <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
          <a class="enlace-rojo small" href="#/torneos/${torneoId}?tab=llave">
            <i class="bi bi-arrow-left"></i> Volver a ${escapar(torneo.nombre)}
          </a>
          <div class="d-flex flex-wrap align-items-center gap-2">
            <span class="chip chip-sm">${escapar(partida.nombre_ronda)} · Partida #${partida.numero}</span>
            ${badgeEstadoPartida(partida)}
          </div>
        </div>

        <div class="sala-cabecera mb-4">
          <div class="text-center mb-3">
            <div class="text-secundario small text-uppercase">${escapar(torneo.nombre)}</div>
            <div class="text-secundario small">
              ${escapar(torneo.formato_texto)} · ${escapar(torneo.videojuego)}
              ${
                partida.fecha_programada
                  ? ` · <i class="bi bi-clock"></i> ${fechaHora(partida.fecha_programada)}`
                  : ""
              }
            </div>
          </div>
          <div class="sala-marcador">
            ${lado(partida.participante1, score1, gano1, "end")}
            <div class="sala-score">${score1}<span class="text-secundario"> : </span>${score2}<small>MARCADOR</small></div>
            ${lado(partida.participante2, score2, gano2, "start")}
          </div>
        </div>

        ${
          partida.estado === "bye"
            ? `<div class="alerta">
                 <div class="alert alert-info mb-4">
                   <i class="bi bi-fast-forward"></i> Esta partida es un pase directo: el participante avanza sin jugar.
                 </div>
               </div>`
            : ""
        }

        ${partida.estado !== "bye" ? cajaResultado(partida, torneo) : ""}
        ${partida.estado !== "bye" ? accionesResultado(partida, torneo) : ""}
      </div>`;

    const recargar = async (mensaje) => {
      const datos = await cargar();
      pintar(datos);
      refrescarNotificaciones({ silencioso: true });
      toast(mensaje, { titulo: "Sala de partida", tipo: "resultado" });
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

    contenedor.querySelector("[data-form-resultado]")?.addEventListener("submit", (evento) => {
      evento.preventDefault();
      const formulario = evento.currentTarget;
      const datos = new FormData(formulario);
      ejecutar(
        formulario.querySelector("button[type=submit]"),
        () =>
          api.post(`/torneos/${torneoId}/partidas/${partidaId}/resultado`, {
            puntaje1: Number(datos.get("puntaje1")),
            puntaje2: Number(datos.get("puntaje2")),
          }),
        "Resultado enviado."
      );
    });

    contenedor.querySelector("[data-confirmar]")?.addEventListener("click", (evento) => {
      ejecutar(
        evento.currentTarget,
        () => api.post(`/torneos/${torneoId}/partidas/${partidaId}/confirmar`),
        "Resultado confirmado."
      );
    });

    contenedor.querySelector("[data-abrir-disputa]")?.addEventListener("click", () => {
      contenedor.querySelector("[data-form-disputa]")?.classList.toggle("d-none");
    });

    contenedor.querySelector("[data-form-disputa]")?.addEventListener("submit", (evento) => {
      evento.preventDefault();
      const motivo = new FormData(evento.currentTarget).get("motivo") || "";
      ejecutar(
        evento.currentTarget.querySelector("button[type=submit]"),
        () =>
          api.post(`/torneos/${torneoId}/partidas/${partidaId}/disputar`, {
            motivo: String(motivo),
          }),
        "Disputa enviada a la organización."
      );
    });

    contenedor.querySelector("[data-form-resolver]")?.addEventListener("submit", (evento) => {
      evento.preventDefault();
      const datos = new FormData(evento.currentTarget);
      ejecutar(
        evento.currentTarget.querySelector("button[type=submit]"),
        () =>
          api.post(`/torneos/${torneoId}/partidas/${partidaId}/resolver`, {
            puntaje1: Number(datos.get("puntaje1")),
            puntaje2: Number(datos.get("puntaje2")),
          }),
        "Marcador resuelto."
      );
    });

    contenedor.querySelector("[data-rechazar]")?.addEventListener("click", (evento) => {
      if (!confirmar("Se borrará el resultado cargado y la partida volverá a estar pendiente.", "Rechazar")) return;
      ejecutar(
        evento.currentTarget,
        () => api.post(`/torneos/${torneoId}/partidas/${partidaId}/rechazar`),
        "Resultado rechazado."
      );
    });

    contenedor.querySelector("[data-form-programar]")?.addEventListener("submit", (evento) => {
      evento.preventDefault();
      const valor = new FormData(evento.currentTarget).get("fecha_programada");
      ejecutar(
        evento.currentTarget.querySelector("button[type=submit]"),
        () =>
          api.post(`/torneos/${torneoId}/partidas/${partidaId}/programar`, {
            fecha_programada: valor || null,
          }),
        "Horario guardado."
      );
    });
  }

  try {
    pintar(await cargar());
  } catch (error) {
    if (error.status === 404) throw error;
    toast(mensajeError(error), { titulo: "No se pudo abrir la sala", tipo: "disputa" });
    throw error;
  }
}
