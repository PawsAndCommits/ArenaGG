import { registrar } from "../auth.js";
import { toast } from "../layout.js";
import {
  escapar,
  juegosFavoritos,
  marcarErrores,
  resumenErrores,
} from "../utils.js";

function destinoSeguro(query) {
  const destino = query.get("redirect") || "/";
  return destino.startsWith("/") && !destino.startsWith("//") ? destino : "/";
}

export async function render(contenedor, { query }) {
  contenedor.innerHTML = `
    <div class="container">
      <div class="row justify-content-center">
        <div class="col-md-8 col-lg-6">
          <div class="tarjeta tarjeta-form">
            <div class="text-center mb-4">
              <span class="marca-icono marca-icono-lg"><i class="bi bi-person-plus"></i></span>
              <h1 class="h3 mt-3">Crear cuenta</h1>
              <p class="text-secundario mb-0">Registrate como jugador y empezá a competir</p>
            </div>
            <div data-aviso></div>
            <form id="formRegistro" novalidate>
              <div class="mb-3">
                <label class="form-label" for="username">Nombre de usuario <span class="text-danger">*</span></label>
                <input class="form-control" id="username" name="username" required maxlength="30"
                       autocomplete="username" autofocus>
                <div class="form-text">Entre 3 y 30 caracteres: letras, números, punto, guion o guion bajo.</div>
              </div>
              <div class="mb-3">
                <label class="form-label" for="email">Correo electrónico <span class="text-danger">*</span></label>
                <input class="form-control" type="email" id="email" name="email" required autocomplete="email">
              </div>
              <div class="row">
                <div class="col-sm-6 mb-3">
                  <label class="form-label" for="password">Contraseña <span class="text-danger">*</span></label>
                  <input class="form-control" type="password" id="password" name="password" required
                         autocomplete="new-password">
                </div>
                <div class="col-sm-6 mb-3">
                  <label class="form-label" for="password_confirmacion">Repetir contraseña <span class="text-danger">*</span></label>
                  <input class="form-control" type="password" id="password_confirmacion"
                         name="password_confirmacion" required autocomplete="new-password">
                </div>
              </div>
              <div class="form-text mb-3">Mínimo 8 caracteres, con al menos una letra y un número.</div>
              <div class="mb-3">
                <label class="form-label" for="juegos_favoritos">Juegos favoritos</label>
                <input class="form-control" id="juegos_favoritos" name="juegos_favoritos"
                       placeholder="CS 1.6, Dota 2, Valorant">
                <div class="form-text">Separá los juegos con comas (opcional, máximo 10).</div>
              </div>
              <button class="btn btn-rojo w-100" type="submit">
                <i class="bi bi-person-check"></i> Crear cuenta
              </button>
            </form>
            <p class="text-center text-secundario small mt-4 mb-0">
              ¿Ya tenés cuenta? <a class="enlace-rojo" href="#/login">Iniciá sesión</a>
            </p>
          </div>
        </div>
      </div>
    </div>`;

  const formulario = contenedor.querySelector("#formRegistro");
  const aviso = contenedor.querySelector("[data-aviso]");

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    aviso.innerHTML = "";
    marcarErrores(formulario, {});
    const datos = new FormData(formulario);
    const boton = formulario.querySelector("button[type=submit]");
    boton.disabled = true;
    boton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Creando cuenta…';

    try {
      await registrar({
        username: String(datos.get("username") || "").trim(),
        email: String(datos.get("email") || "").trim(),
        password: String(datos.get("password") || ""),
        password_confirmacion: String(datos.get("password_confirmacion") || ""),
        juegos_favoritos: juegosFavoritos(datos.get("juegos_favoritos")),
      });
      toast("Tu cuenta está lista. ¡Bienvenido a ArenaGG!", {
        titulo: "Cuenta creada",
        tipo: "resultado",
      });
      window.location.hash = `#${destinoSeguro(query)}`;
    } catch (error) {
      marcarErrores(formulario, error.errores || {});
      aviso.innerHTML = `<div class="alert alert-danger">${resumenErrores(error)
        .map((mensaje) => `<div>${escapar(mensaje)}</div>`)
        .join("")}</div>`;
      boton.disabled = false;
      boton.innerHTML = '<i class="bi bi-person-check"></i> Crear cuenta';
    }
  });
}
