// Interacciones de la interfaz (sin dependencias además de Bootstrap).
document.addEventListener("DOMContentLoaded", () => {
  // Confirmación antes de acciones destructivas: <form data-confirmar="mensaje">
  document.querySelectorAll("form[data-confirmar]").forEach((form) => {
    form.addEventListener("submit", (evento) => {
      if (!window.confirm(form.dataset.confirmar)) evento.preventDefault();
    });
  });

  // Filtros que se envían solos al cambiar
  document.querySelectorAll("select.js-autoenviar").forEach((select) => {
    select.addEventListener("change", () => select.form.submit());
  });

  // Mostrar / ocultar contraseña
  document.querySelectorAll(".js-ver-password").forEach((boton) => {
    boton.addEventListener("click", () => {
      const input = document.getElementById(boton.dataset.objetivo);
      const visible = input.type === "text";
      input.type = visible ? "password" : "text";
      boton.innerHTML = `<i class="bi bi-eye${visible ? "" : "-slash"}"></i>`;
    });
  });

  // Formulario de torneo: el campo "jugadores por equipo" solo aplica a equipos
  const modalidad = document.getElementById("modalidad");
  const soloEquipos = document.querySelectorAll(".js-solo-equipos");
  if (modalidad && soloEquipos.length) {
    const actualizar = () => {
      soloEquipos.forEach((el) => el.classList.toggle("d-none", modalidad.value !== "equipos"));
    };
    modalidad.addEventListener("change", actualizar);
    actualizar();
  }

  // Los avisos de éxito se cierran solos
  document.querySelectorAll(".avisos .alert-success, .avisos .alert-info").forEach((alerta) => {
    setTimeout(() => bootstrap.Alert.getOrCreateInstance(alerta).close(), 6000);
  });

  // WebSocket: alerta + sonido al iniciar torneo
  if (typeof io !== "undefined") {
    try {
      const socket = io();
      socket.on("torneo_iniciado", (data) => {
        const nombre = data && data.nombre ? data.nombre : "el torneo";
        // Notificación Bootstrap
        const contenedor = document.querySelector(".avisos") || document.querySelector("main .container");
        if (contenedor) {
          const alerta = document.createElement("div");
          alerta.className = "alert alert-success alert-dismissible fade show";
          alerta.setAttribute("role", "alert");
          alerta.innerHTML = `<i class="bi bi-bell-fill"></i> ¡${nombre} ha iniciado! Se generaron los cruces.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Cerrar"></button>`;
          contenedor.prepend(alerta);
          setTimeout(() => bootstrap.Alert.getOrCreateInstance(alerta).close(), 8000);
        }
        // Sonido
        try {
          const audio = new Audio("/static/audio/torneo-iniciado.mp3");
          audio.volume = 0.7;
          audio.play().catch(() => {});
        } catch (e) {}
      });

      socket.on("match_ready", (data) => {
        try {
          const info = document.getElementById("matchReadyInfo");
          if (info) {
            const torneo = data && data.torneo ? data.torneo : "";
            const partida = data && data.partida_numero ? `Partida #${data.partida_numero}` : "Tu partida";
            let texto = `${partida}${torneo ? " · " + torneo : ""}`;
            if (data && data.servidor_ip && data.servidor_puerto) {
              texto += ` · conectate a ${data.servidor_ip}:${data.servidor_puerto}`;
              const boton = document.getElementById("matchReadyConnect");
              if (boton) {
                boton.href = `steam://connect/${data.servidor_ip}:${data.servidor_puerto}`;
                boton.classList.remove("d-none");
              }
            }
            if (data && data.mensaje) texto += ` · ${data.mensaje}`;
            info.textContent = texto;
          }
          const modalEl = document.getElementById("matchReadyModal");
          if (modalEl && typeof bootstrap !== "undefined") {
            new bootstrap.Modal(modalEl).show();
          }
          const faceit = document.getElementById("faceitAlert");
          if (faceit) {
            faceit.currentTime = 0;
            faceit.volume = 0.9;
            faceit.play().catch(() => {});
          }
        } catch (e) {}
      });
    } catch (e) {}
  }
});
