(function () {
  "use strict";

  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
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

  function $(selector, raiz) {
    return (raiz || document).querySelector(selector);
  }

  function todos(selector, raiz) {
    return Array.from((raiz || document).querySelectorAll(selector));
  }

  function sonar() {
    const audio = $("#faceitAlert");
    if (!audio) return;
    try {
      audio.currentTime = 0;
      audio.volume = 0.85;
      audio.play().catch(() => {});
    } catch (_error) {}
  }

  function actualizarContador(cantidad) {
    todos("[data-notificaciones-contador]").forEach((elemento) => {
      elemento.textContent = cantidad > 99 ? "99+" : String(cantidad);
      elemento.classList.toggle("d-none", cantidad <= 0);
    });
  }

  function abrirNotificacion(id) {
    if (!id) return;
    const formulario = document.createElement("form");
    formulario.method = "post";
    formulario.action = `/notificaciones/${id}/abrir`;
    const campo = document.createElement("input");
    campo.type = "hidden";
    campo.name = "csrf_token";
    campo.value = csrf;
    formulario.appendChild(campo);
    document.body.appendChild(formulario);
    formulario.submit();
  }

  function mostrarToast(datos) {
    const contenedor = $("#toastStack");
    if (!contenedor) return;
    const tarjeta = document.createElement("div");
    tarjeta.className = "toast-faceit";
    tarjeta.innerHTML = `
      <div class="toast-faceit-icono"><i class="bi bi-${iconos[datos.tipo] || "bell"}"></i></div>
      <div class="flex-grow-1 min-w-0">
        <div class="toast-faceit-titulo"></div>
        <div class="toast-faceit-mensaje"></div>
        <button type="button" class="toast-faceit-accion d-none">Ver detalle <i class="bi bi-arrow-right"></i></button>
      </div>
      <button type="button" class="btn-close btn-close-white ms-2" aria-label="Cerrar"></button>
    `;
    $(".toast-faceit-titulo", tarjeta).textContent = datos.titulo || "Aviso";
    $(".toast-faceit-mensaje", tarjeta).textContent = datos.mensaje || "";
    const accion = $(".toast-faceit-accion", tarjeta);
    if (datos.url) {
      accion.classList.remove("d-none");
      accion.addEventListener("click", () => abrirNotificacion(datos.id));
    }
    $(".btn-close", tarjeta).addEventListener("click", () => tarjeta.remove());
    contenedor.appendChild(tarjeta);
    requestAnimationFrame(() => tarjeta.classList.add("visible"));
    setTimeout(() => {
      tarjeta.classList.remove("visible");
      setTimeout(() => tarjeta.remove(), 250);
    }, 7000);
  }

  function iniciarPestanas() {
    const disparadores = todos('[data-bs-toggle="tab"]');
    if (!disparadores.length) return;
    const mostrarPorHash = () => {
      const hash = window.location.hash;
      if (!hash || hash.length < 2) return;
      const destino = document.querySelector(
        `[data-bs-toggle="tab"][data-bs-target="${hash}"], [data-bs-toggle="tab"][href="${hash}"]`
      );
      if (destino) bootstrap.Tab.getOrCreateInstance(destino).show();
    };
    mostrarPorHash();
    disparadores.forEach((disparador) => {
      disparador.addEventListener("shown.bs.tab", (evento) => {
        const destino =
          evento.target.getAttribute("data-bs-target") || evento.target.getAttribute("href");
        if (destino && destino.startsWith("#")) {
          history.replaceState(null, "", destino);
        }
      });
    });
    window.addEventListener("hashchange", mostrarPorHash);
  }

  document.addEventListener("DOMContentLoaded", () => {
    todos("form[data-confirmar]").forEach((formulario) => {
      formulario.addEventListener("submit", (evento) => {
        if (!window.confirm(formulario.dataset.confirmar)) evento.preventDefault();
      });
    });

    todos("select.js-autoenviar").forEach((select) => {
      select.addEventListener("change", () => select.form.submit());
    });

    todos(".js-ver-password").forEach((boton) => {
      boton.addEventListener("click", () => {
        const input = document.getElementById(boton.dataset.objetivo);
        if (!input) return;
        const visible = input.type === "text";
        input.type = visible ? "password" : "text";
        boton.innerHTML = `<i class="bi bi-eye${visible ? "" : "-slash"}"></i>`;
      });
    });

    const modalidad = $("#modalidad");
    const soloEquipos = todos(".js-solo-equipos");
    if (modalidad && soloEquipos.length) {
      const actualizar = () => {
        soloEquipos.forEach((elemento) => {
          elemento.classList.toggle("d-none", modalidad.value !== "equipos");
        });
      };
      modalidad.addEventListener("change", actualizar);
      actualizar();
    }

    todos(".avisos .alert-success, .avisos .alert-info").forEach((alerta) => {
      setTimeout(() => bootstrap.Alert.getOrCreateInstance(alerta).close(), 5500);
    });

    iniciarPestanas();

    if (typeof io === "undefined") return;
    const socket = io();
    const torneoId = $("main[data-torneo-id]")?.dataset.torneoId;
    if (torneoId) {
      socket.emit("unirse_torneo", { torneo_id: torneoId });
    }

    socket.on("notificacion", (datos) => {
      if (!datos) return;
      const contador = $("[data-notificaciones-contador]");
      const actual = parseInt(contador?.textContent || "0", 10) || 0;
      actualizarContador(actual + 1);
      mostrarToast(datos);
      sonar();
    });

    socket.on("match_ready", (datos) => {
      if (!datos) return;
      const texto = [datos.partida_numero ? `Partida #${datos.partida_numero}` : "", datos.torneo || "", datos.mensaje || ""]
        .filter(Boolean)
        .join(" · ");
      const info = $("#matchReadyInfo");
      if (info) info.textContent = texto || "Ya podés jugar tu partida.";
      const enlace = $("#matchReadyLink");
      if (enlace) {
        enlace.href = datos.url || (datos.torneo_id && datos.partida_id ? `/torneos/${datos.torneo_id}/partidas/${datos.partida_id}` : "#");
      }
      sonar();
      const modal = $("#matchReadyModal");
      if (modal) bootstrap.Modal.getOrCreateInstance(modal).show();
    });

    socket.on("torneo_actualizado", (datos) => {
      if (!torneoId || !datos || String(datos.torneo_id) !== String(torneoId)) return;
      if ($(".modal.show")) return;
      const activo = document.activeElement;
      if (activo && ["INPUT", "TEXTAREA", "SELECT"].includes(activo.tagName) && activo.form) return;
      window.location.reload();
    });
  });
})();
