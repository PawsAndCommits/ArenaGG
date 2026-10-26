import {
  escapar,
  fechaHora,
  fechaCorta,
  iconoEstado,
  iniciales as calcularIniciales,
  racha as rachaHtml,
} from "./utils.js";

export function escudo(nombre, { iniciales, tamano = "" } = {}) {
  const letras = iniciales || calcularIniciales(nombre);
  return `<span class="escudo ${tamano}" aria-hidden="true">${escapar(letras)}</span>`;
}

export function avatar(nombre, tamano = "avatar-sm") {
  return `<span class="avatar ${tamano}" aria-hidden="true">${escapar(
    calcularIniciales(nombre).slice(0, 1)
  )}</span>`;
}

export function insignia(participante, tamano = "") {
  if (!participante) return escudo("?", { iniciales: "?", tamano: "escudo-sm" });
  if (participante.equipo_id) {
    return escudo(participante.nombre, {
      tamano,
      iniciales: calcularIniciales(participante.nombre),
    });
  }
  return avatar(participante.nombre, tamano ? tamano.replace("escudo-", "avatar-") : "avatar-sm");
}

export function nombreParticipante(participante) {
  if (!participante) return '<span class="text-secundario">Por definir</span>';
  const enlace = participante.equipo_id
    ? `#/equipos/${participante.equipo_id}`
    : `#/usuarios/${participante.usuario_id}`;
  return `<a class="enlace-jugador" href="${enlace}">${escapar(participante.nombre)}</a>`;
}

export function badgeEstadoTorneo(torneo) {
  return `<span class="${`estado estado-${torneo.estado}`}"><i class="bi bi-${iconoEstado(
    torneo.estado
  )}"></i> ${escapar(torneo.estado_texto)}</span>`;
}

export function badgeEstadoPartida(partida) {
  return `<span class="estado-partida estado-partida-${partida.estado_clase}">${escapar(
    partida.estado_texto
  )}</span>`;
}

export function tarjetaTorneo(torneo, { destacada = false } = {}) {
  const completa = torneo.esta_completo;
  const iconoModalidad = torneo.modalidad === "equipos" ? "people" : "person";
  return `
    <a href="#/torneos/${torneo.id}" class="tarjeta tarjeta-torneo ${
      destacada ? "tarjeta-destacada" : ""
    } h-100">
      <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
        <span class="juego"><i class="bi bi-joystick"></i> ${escapar(torneo.videojuego)}</span>
        ${badgeEstadoTorneo(torneo)}
      </div>
      <h3 class="tarjeta-titulo">
        ${torneo.destacado ? '<i class="bi bi-star-fill text-warning small"></i> ' : ""}
        ${escapar(torneo.nombre)}
      </h3>
      ${
        torneo.descripcion
          ? `<p class="text-secundario small mb-3 recorte-2">${escapar(torneo.descripcion)}</p>`
          : ""
      }
      <div class="meta">
        <span><i class="bi bi-calendar-event"></i> ${fechaCorta(torneo.fecha)} · ${escapar(
          fechaHora(torneo.fecha).split(" · ")[1] || ""
        )}</span>
        <span><i class="bi bi-${iconoModalidad}"></i> ${escapar(torneo.modalidad_texto)}</span>
        <span><i class="bi bi-collection"></i> ${escapar(torneo.formato_texto)}</span>
      </div>
      <div class="mt-3">
        <div class="d-flex justify-content-between small mb-1">
          <span>${torneo.inscriptos}/${torneo.cupo_maximo} inscriptos</span>
          <span class="${completa ? "text-danger" : "text-rojo"}">
            ${completa ? "Completo" : `${torneo.cupos_disponibles} cupos libres`}
          </span>
        </div>
        <div class="progress progress-fino">
          <div class="progress-bar barra-roja" style="width: ${torneo.porcentaje_ocupado}%"></div>
        </div>
      </div>
    </a>`;
}

export function estadoVacio(icono, mensaje) {
  return `<div class="vacio"><i class="bi bi-${icono}"></i><p class="mb-0">${escapar(
    mensaje
  )}</p></div>`;
}

export function cargando(texto = "Cargando…") {
  return `<div class="cargando"><div class="spinner-border" role="status" aria-hidden="true"></div><p class="mt-3 mb-0">${escapar(
    texto
  )}</p></div>`;
}

export function errorPagina(titulo, mensaje) {
  return `
    <div class="error-pagina text-center">
      <div class="error-codigo text-gradiente">${escapar(titulo)}</div>
      <p class="text-secundario">${escapar(mensaje)}</p>
      <a class="btn btn-rojo" href="#/"><i class="bi bi-house"></i> Volver al inicio</a>
    </div>`;
}

export function bannerCampeon(campeon) {
  if (!campeon) return "";
  return `
    <div class="banner-campeon mb-4">
      <i class="bi bi-trophy-fill"></i>
      <div>
        <div class="text-secundario small text-uppercase">Campeón</div>
        <div class="banner-campeon-nombre">${escapar(campeon.nombre)}</div>
      </div>
    </div>`;
}

export function listaParticipantes(participantes) {
  if (!participantes.length) {
    return estadoVacio("people", "Todavía no hay participantes inscriptos.");
  }
  return `
    <ul class="lista-participantes">
      ${participantes
        .map((participante, indice) => {
          const enlace = participante.equipo
            ? `#/equipos/${participante.equipo.id}`
            : `#/usuarios/${participante.usuario.id}`;
          const roster = (participante.roster || [])
            .map((jugador) =>
              jugador.id === (participante.equipo ? participante.equipo.capitan_id : participante.usuario.id)
                ? `<span class="text-rojo">${escapar(jugador.username)} (C)</span>`
                : `<span>${escapar(jugador.username)}</span>`
            )
            .join("");
          return `
            <li>
              <span class="puesto">${indice + 1}</span>
              ${
                participante.equipo
                  ? escudo(participante.nombre, { tamano: "escudo-sm" })
                  : avatar(participante.nombre)
              }
              <div class="flex-grow-1 min-w-0">
                <a class="enlace-jugador" href="${enlace}">${escapar(participante.nombre)}</a>
                ${roster ? `<div class="roster-mini mt-1">${roster}</div>` : ""}
              </div>
              <span class="text-secundario small d-none d-sm-inline">${fechaCorta(
                participante.inscripto_en
              )}</span>
            </li>`;
        })
        .join("")}
    </ul>`;
}

export function tablaPosiciones(posiciones) {
  if (!posiciones.length) {
    return estadoVacio("table", "La tabla se completa cuando arranca el torneo.");
  }
  return `
    <div class="table-responsive">
      <table class="table tabla-gamer align-middle">
        <thead>
          <tr>
            <th>#</th>
            <th>Participante</th>
            <th class="text-center">PJ</th>
            <th class="text-center">G</th>
            <th class="text-center">P</th>
            <th class="text-center">Mapas</th>
            <th class="text-center">Dif</th>
            <th class="text-center">Winrate</th>
            <th class="text-center">Últimos</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          ${posiciones
            .map(
              (fila) => `
            <tr>
              <td><span class="puesto ${
                fila.posicion <= 3 ? `puesto-${fila.posicion}` : ""
              }">${fila.posicion}</span></td>
              <td>
                <a class="enlace-jugador" href="#/usuarios/${fila.usuario_id}">${escapar(
                  fila.nombre
                )}</a>
                ${fila.equipo ? `<div class="text-secundario small">${escapar(fila.equipo)}</div>` : ""}
              </td>
              <td class="text-center">${fila.partidas_jugadas}</td>
              <td class="text-center text-success">${fila.victorias}</td>
              <td class="text-center text-danger">${fila.derrotas}</td>
              <td class="text-center">${fila.mapas_favor}-${fila.mapas_contra}</td>
              <td class="text-center">${fila.diferencia > 0 ? "+" : ""}${fila.diferencia}</td>
              <td class="text-center">${fila.winrate}%</td>
              <td class="text-center">${rachaHtml(fila.ultimos)}</td>
              <td><span class="chip chip-sm">${escapar(fila.estado)}</span></td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>`;
}

function filaBracket(participante, puntaje, esGanador) {
  return `
    <div class="bracket-equipo ${esGanador ? "ganador" : ""}">
      <span class="d-flex align-items-center gap-2 min-w-0">
        ${insignia(participante, "escudo-sm")}
        <span class="text-truncate">${participante ? escapar(participante.nombre) : "Por definir"}</span>
      </span>
      <span class="marcador">${puntaje ?? "–"}</span>
    </div>`;
}

export function bracket(partidas, torneoId) {
  if (!partidas.length) {
    return estadoVacio("diagram-3", "La llave se genera cuando el administrador inicia el torneo.");
  }
  const rondas = new Map();
  partidas.forEach((partida) => {
    if (!rondas.has(partida.ronda)) rondas.set(partida.ronda, []);
    rondas.get(partida.ronda).push(partida);
  });
  return `
    <div class="bracket-tablero">
      ${[...rondas.entries()]
        .sort(([a], [b]) => a - b)
        .map(([numeroRonda, lista]) => {
          const titulo = lista[0]?.nombre_ronda || `Ronda ${numeroRonda}`;
          return `
          <div class="bracket-columna">
            <div class="bracket-columna-titulo">${escapar(titulo)}</div>
            <div class="bracket-lista">
              ${lista
                .map((partida) => {
                  const resultado = partida.resultado;
                  const gano1 = partida.ganador && partida.participante1 && partida.ganador.inscripcion_id === partida.participante1.inscripcion_id;
                  const gano2 = partida.ganador && partida.participante2 && partida.ganador.inscripcion_id === partida.participante2.inscripcion_id;
                  return `
                    <a class="bracket-carta" href="#/torneos/${torneoId}/partidas/${partida.id}">
                      <div class="bracket-carta-top">
                        <span>Partida #${partida.numero}</span>
                        ${badgeEstadoPartida(partida)}
                      </div>
                      ${filaBracket(partida.participante1, resultado?.puntaje1, gano1)}
                      ${filaBracket(partida.participante2, resultado?.puntaje2, gano2)}
                    </a>`;
                })
                .join("")}
            </div>
          </div>`;
        })
        .join("")}
    </div>`;
}

export function paginacion(pagina, paginas, { parametro = "pagina" } = {}) {
  if (paginas <= 1) return "";
  const inicio = Math.max(1, Math.min(pagina - 2, paginas - 4));
  const fin = Math.min(paginas, inicio + 4);
  const botones = [];
  for (let numero = inicio; numero <= fin; numero += 1) {
    botones.push(`
      <li class="page-item ${numero === pagina ? "active" : ""}">
        <button class="page-link" type="button" data-${parametro}="${numero}">${numero}</button>
      </li>`);
  }
  return `
    <nav aria-label="Paginación">
      <ul class="pagination pagination-arena justify-content-center mt-3">
        <li class="page-item ${pagina <= 1 ? "disabled" : ""}">
          <button class="page-link" type="button" data-${parametro}="${pagina - 1}">
            <i class="bi bi-chevron-left"></i>
          </button>
        </li>
        ${botones.join("")}
        <li class="page-item ${pagina >= paginas ? "disabled" : ""}">
          <button class="page-link" type="button" data-${parametro}="${pagina + 1}">
            <i class="bi bi-chevron-right"></i>
          </button>
        </li>
      </ul>
    </nav>`;
}
