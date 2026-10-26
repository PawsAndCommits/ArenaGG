import { api } from "../api.js";
import {
  actualizarUsuario,
  cerrarSesion,
  estaAutenticado,
  usuarioActual,
} from "../auth.js";
import { avatar } from "../components.js";
import { toast } from "../layout.js";
import {
  escapar,
  fecha,
  juegosFavoritos,
  marcarErrores,
  resumenErrores,
} from "../utils.js";

const ESTADOS = {
  proximamente: "Próximamente",
  inscripciones_abiertas: "Inscripciones abiertas",
  en_curso: "En curso",
  finalizado: "Finalizado",
};

export async function render(contenedor, { params, query, ruta }) {
  const propio = !params.id;
  if (propio && !estaAutenticado()) {
    window.location.hash = `#/login?redirect=${encodeURIComponent("/perfil")}`;
    return;
  }
  const id = params.id || usuarioActual()?.id;
  const esPropio = usuarioActual()?.id === Number(id);

  async function cargar() {
    const [perfil, historial] = await Promise.all([
      propio ? api.get("/usuarios/me") : api.get(`/usuarios/${id}`),
      api.get(`/usuarios/${id}/historial`),
    ]);
    return { perfil, historial: historial.historial || [] };
  }

  function pintar({ perfil, historial }) {
    const juegos = juegosFavoritos(perfil.juegos_favoritos);
    contenedor.innerHTML = `
      <div class="container">
        <a class="enlace-rojo small d-inline-block mb-3" href="#/torneos">
          <i class="bi bi-arrow-left"></i> Volver a torneos
        </a>

        <div class="tarjeta perfil-cabecera mb-4">
          <div class="d-flex flex-column flex-md-row align-items-md-center gap-3">
            ${avatar(perfil.username, "avatar-xl")}
            <div class="flex-grow-1">
              <div class="d-flex flex-wrap align-items-center gap-2 mb-1">
                <h1 class="h2 mb-0">${escapar(perfil.username)}</h1>
                <span class="badge ${perfil.rol === "admin" ? "text-bg-rojo" : "text-bg-secondary"}">
                  ${perfil.rol === "admin" ? "Administrador" : "Jugador"}
                </span>
              </div>
              <div class="meta">
                <span><i class="bi bi-calendar3"></i> Miembro desde ${fecha(perfil.creado_en)}</span>
                ${perfil.email && (esPropio || usuarioActual()?.rol === "admin") ? `<span><i class="bi bi-envelope"></i> ${escapar(perfil.email)}</span>` : ""}
                <span><i class="bi bi-trophy"></i> ${historial.length} torneo${historial.length === 1 ? "" : "s"}</span>
              </div>
              ${
                juegos.length
                  ? `<div class="d-flex flex-wrap gap-2 mt-3">${juegos
                      .map(
                        (juego) =>
                          `<span class="juego"><i class="bi bi-joystick"></i> ${escapar(juego)}</span>`
                      )
                      .join("")}</div>`
                  : ""
              }
            </div>
            ${
              esPropio
                ? `<a class="btn btn-fantasma" href="#/equipos"><i class="bi bi-people"></i> Mis equipos</a>`
                : ""
            }
          </div>
        </div>

        <div class="row g-4">
          <div class="col-lg-7">
            <div class="tarjeta">
              <h2 class="h5 mb-3"><i class="bi bi-clock-history"></i> Historial de torneos</h2>
              ${
                historial.length
                  ? `<div class="table-responsive">
                      <table class="table tabla-gamer align-middle">
                        <thead>
                          <tr><th>Torneo</th><th>Juego</th><th>Participación</th><th>Fecha</th><th>Estado</th></tr>
                        </thead>
                        <tbody>
                          ${historial
                            .map(
                              (item) => `
                              <tr>
                                <td><a class="enlace-jugador" href="#/torneos/${item.torneo.id}">${escapar(
                                  item.torneo.nombre
                                )}</a></td>
                                <td class="text-secundario small">${escapar(item.torneo.videojuego)}</td>
                                <td>${escapar(item.nombre)}</td>
                                <td class="text-secundario small">${fecha(item.torneo.fecha)}</td>
                                <td><span class="estado estado-${item.torneo.estado}">${escapar(
                                  ESTADOS[item.torneo.estado] || item.torneo.estado
                                )}</span></td>
                              </tr>`
                            )
                            .join("")}
                        </tbody>
                      </table>
                    </div>`
                  : '<div class="vacio"><i class="bi bi-inbox"></i><p class="mb-0">Todavía no participaste de un torneo.</p></div>'
              }
            </div>
          </div>

          <div class="col-lg-5">
            ${
              esPropio
                ? `<div class="tarjeta" id="tarjetaEdicion">
                     <h2 class="h5 mb-3"><i class="bi bi-pencil-square"></i> Editar perfil</h2>
                     <div data-aviso-perfil></div>
                     <form id="formPerfil" novalidate>
                       <div class="mb-3">
                         <label class="form-label" for="username">Nombre de usuario</label>
                         <input class="form-control" id="username" name="username" required maxlength="30"
                                value="${escapar(perfil.username)}">
                       </div>
                       <div class="mb-3">
                         <label class="form-label" for="email">Correo electrónico</label>
                         <input class="form-control" type="email" id="email" name="email"
                                value="${escapar(perfil.email || "")}">
                       </div>
                       <div class="mb-3">
                         <label class="form-label" for="juegos_favoritos">Juegos favoritos</label>
                         <input class="form-control" id="juegos_favoritos" name="juegos_favoritos"
                                value="${escapar(juegos.join(", "))}" placeholder="CS 1.6, Dota 2, Valorant">
                       </div>
                       <div class="form-check mb-2">
                         <input class="form-check-input" type="checkbox" id="cambiarPassword" name="cambiarPassword">
                         <label class="form-check-label" for="cambiarPassword">Cambiar contraseña</label>
                       </div>
                       <div class="d-none" data-campos-password>
                         <div class="mb-3">
                           <label class="form-label" for="password_actual">Contraseña actual</label>
                           <input class="form-control" type="password" id="password_actual" name="password_actual"
                                  autocomplete="current-password">
                         </div>
                         <div class="mb-3">
                           <label class="form-label" for="password">Nueva contraseña</label>
                           <input class="form-control" type="password" id="password" name="password"
                                  autocomplete="new-password">
                         </div>
                         <div class="mb-3">
                           <label class="form-label" for="password_confirmacion">Repetir nueva contraseña</label>
                           <input class="form-control" type="password" id="password_confirmacion"
                                  name="password_confirmacion" autocomplete="new-password">
                         </div>
                       </div>
                       <button class="btn btn-rojo w-100" type="submit">
                         <i class="bi bi-check2"></i> Guardar cambios
                       </button>
                     </form>
                   </div>`
                : `<div class="tarjeta">
                     <h2 class="h5 mb-3"><i class="bi bi-info-circle"></i> Sobre el jugador</h2>
                     <p class="text-secundario small mb-0">
                       ${escapar(perfil.username)} compite en ArenaGG desde ${fecha(perfil.creado_en)}.
                     </p>
                   </div>`
            }
          </div>
        </div>
      </div>`;

    if (!esPropio) return;

    const formulario = contenedor.querySelector("#formPerfil");
    const aviso = contenedor.querySelector("[data-aviso-perfil]");
    const casilla = contenedor.querySelector("#cambiarPassword");
    const campos = contenedor.querySelector("[data-campos-password]");

    casilla.addEventListener("change", () => {
      campos.classList.toggle("d-none", !casilla.checked);
      campos.querySelectorAll("input").forEach((entrada) => {
        entrada.required = casilla.checked;
      });
    });

    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      aviso.innerHTML = "";
      marcarErrores(formulario, {});
      const datos = new FormData(formulario);
      const cuerpo = {
        username: String(datos.get("username") || "").trim(),
        email: String(datos.get("email") || "").trim(),
        juegos_favoritos: juegosFavoritos(datos.get("juegos_favoritos")),
      };
      const cambiaPassword = casilla.checked;
      if (cambiaPassword) {
        cuerpo.password_actual = String(datos.get("password_actual") || "");
        cuerpo.password = String(datos.get("password") || "");
        cuerpo.password_confirmacion = String(datos.get("password_confirmacion") || "");
      }

      const boton = formulario.querySelector("button[type=submit]");
      boton.disabled = true;
      try {
        const actualizado = await api.put(`/usuarios/${perfil.id}`, cuerpo);
        if (cambiaPassword) {
          cerrarSesion({ motivo: "manual" });
          toast("Contraseña actualizada. Iniciá sesión con la nueva clave.", {
            titulo: "Sesión cerrada",
            tipo: "resultado",
          });
          window.location.hash = `#/login?redirect=${encodeURIComponent("/perfil")}`;
          return;
        }
        actualizarUsuario(actualizado);
        toast("Perfil actualizado.", { titulo: "Tus datos", tipo: "resultado" });
      } catch (error) {
        marcarErrores(formulario, error.errores || {});
        aviso.innerHTML = `<div class="alert alert-danger">${resumenErrores(error)
          .map((mensaje) => `<div>${escapar(mensaje)}</div>`)
          .join("")}</div>`;
        boton.disabled = false;
      }
    });
  }

  pintar(await cargar());
}
