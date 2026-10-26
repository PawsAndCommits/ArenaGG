const FORMATO_FECHA = new Intl.DateTimeFormat("es-AR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const FORMATO_FECHA_CORTA = new Intl.DateTimeFormat("es-AR", {
  day: "2-digit",
  month: "2-digit",
});

const FORMATO_HORA = new Intl.DateTimeFormat("es-AR", {
  hour: "2-digit",
  minute: "2-digit",
});

export function escapar(valor) {
  return String(valor ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function aFecha(iso) {
  if (!iso) return null;
  const fecha = new Date(iso);
  return Number.isNaN(fecha.getTime()) ? null : fecha;
}

export function fecha(iso) {
  const valor = aFecha(iso);
  return valor ? FORMATO_FECHA.format(valor) : "Sin fecha";
}

export function fechaCorta(iso) {
  const valor = aFecha(iso);
  return valor ? FORMATO_FECHA_CORTA.format(valor) : "—";
}

export function hora(iso) {
  const valor = aFecha(iso);
  return valor ? FORMATO_HORA.format(valor) : "";
}

export function fechaHora(iso) {
  const valor = aFecha(iso);
  return valor ? `${FORMATO_FECHA.format(valor)} · ${FORMATO_HORA.format(valor)}` : "Sin fecha";
}

export function fechaInput(iso) {
  if (!iso) return "";
  return String(iso).slice(0, 16);
}

export function inputAFecha(valor) {
  const limpio = String(valor || "").trim();
  return limpio ? limpio : null;
}

export function fechaRelativa(iso) {
  const valor = aFecha(iso);
  if (!valor) return "";
  const diferencia = Date.now() - valor.getTime();
  const minutos = Math.floor(diferencia / 60000);
  if (minutos < 1) return "Ahora";
  if (minutos < 60) return `Hace ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `Hace ${horas} h`;
  const dias = Math.floor(horas / 24);
  if (dias < 7) return `Hace ${dias} d`;
  return fechaCorta(iso);
}

export function iniciales(nombre) {
  const partes = String(nombre || "")
    .replaceAll("-", " ")
    .split(" ")
    .filter(Boolean);
  if (!partes.length) return "GG";
  return partes
    .slice(0, 2)
    .map((parte) => parte[0])
    .join("")
    .toUpperCase();
}

export function iconoNotificacion(tipo) {
  const iconos = {
    partida: "controller",
    resultado: "clipboard-check",
    resultado_pendiente: "hourglass-split",
    resultado_rechazado: "arrow-counterclockwise",
    disputa: "exclamation-triangle",
    equipo: "people",
    torneo: "trophy",
    campeon: "trophy",
    eliminado: "x-circle",
    bye: "fast-forward",
    horario: "clock",
    inscripcion: "check-circle",
    servidor: "hdd-network",
  };
  return iconos[tipo] || "bell";
}

export function iconoEstado(estado) {
  const iconos = {
    proximamente: "hourglass-split",
    inscripciones_abiertas: "door-open",
    en_curso: "lightning-charge",
    finalizado: "flag",
  };
  return iconos[estado] || "circle";
}

export function clasesEstado(estado) {
  return `estado estado-${estado}`;
}

export function limpiarErrores(formulario) {
  formulario.querySelectorAll(".is-invalid").forEach((campo) => {
    campo.classList.remove("is-invalid");
  });
  formulario.querySelectorAll(".invalid-feedback[data-dinamico]").forEach((nodo) => {
    nodo.remove();
  });
}

export function marcarErrores(formulario, errores = {}) {
  limpiarErrores(formulario);
  const sinCampo = [];
  Object.entries(errores || {}).forEach(([campo, mensaje]) => {
    const entrada = formulario.querySelector(`[name="${CSS.escape(campo)}"]`);
    if (!entrada) {
      sinCampo.push(`${campo}: ${mensaje}`);
      return;
    }
    entrada.classList.add("is-invalid");
    const aviso = document.createElement("div");
    aviso.className = "invalid-feedback";
    aviso.dataset.dinamico = "1";
    aviso.textContent = mensaje;
    entrada.insertAdjacentElement("afterend", aviso);
  });
  return sinCampo;
}

export function mensajeError(error) {
  if (!error) return "Ocurrió un error inesperado.";
  if (error.detalle) return error.detalle;
  if (error.message) return error.message;
  return "Ocurrió un error inesperado.";
}

export function resumenErrores(error) {
  const partes = [mensajeError(error)];
  if (error && error.errores) {
    Object.values(error.errores).forEach((mensaje) => {
      if (mensaje && !partes.includes(mensaje)) partes.push(mensaje);
    });
  }
  return partes;
}

export function alerta(tipo, mensaje, { cerrable = true } = {}) {
  const boton = cerrable
    ? '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Cerrar"></button>'
    : "";
  const clases = cerrable ? "alert-dismissible fade show" : "";
  return `<div class="alert alert-${tipo} ${clases}" role="alert">${escapar(mensaje)}${boton}</div>`;
}

export function confirmar(mensaje, texto = "Confirmar") {
  return window.confirm(`${mensaje}\n\n${texto}`);
}

export function construirHash(ruta, query = {}) {
  const parametros = new URLSearchParams();
  Object.entries(query).forEach(([clave, valor]) => {
    if (valor !== undefined && valor !== null && valor !== "") {
      parametros.append(clave, valor);
    }
  });
  const cadena = parametros.toString();
  return `#${ruta}${cadena ? `?${cadena}` : ""}`;
}

export function datosFormulario(formulario) {
  const datos = {};
  const elementos = formulario.querySelectorAll("input, select, textarea");
  elementos.forEach((elemento) => {
    if (!elemento.name) return;
    if (elemento.type === "checkbox") {
      datos[elemento.name] = elemento.checked;
    } else if (elemento.type === "number") {
      datos[elemento.name] = elemento.value === "" ? null : Number(elemento.value);
    } else {
      datos[elemento.name] = elemento.value.trim();
    }
  });
  return datos;
}

export function juegosFavoritos(valor) {
  if (Array.isArray(valor)) return valor;
  return String(valor || "")
    .split(",")
    .map((juego) => juego.trim())
    .filter(Boolean);
}

export function racha(ultimos) {
  if (!ultimos) return '<span class="text-secundario">—</span>';
  return `<span class="racha">${[...ultimos]
    .map(
      (resultado) =>
        `<span class="${resultado === "G" ? "g" : "p"}">${escapar(resultado)}</span>`
    )
    .join("")}</span>`;
}
