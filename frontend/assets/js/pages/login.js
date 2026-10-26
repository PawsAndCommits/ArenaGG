import { iniciarSesion } from "../auth.js";
import { toast } from "../layout.js";
import { escapar, marcarErrores, mensajeError, resumenErrores } from "../utils.js";

function destinoSeguro(query) {
  const destino = query.get("redirect") || "/";
  return destino.startsWith("/") && !destino.startsWith("//") ? destino : "/";
}

export async function render(contenedor, { query }) {
  contenedor.innerHTML = `
    <div class="container">
      <div class="row justify-content-center">
        <div class="col-md-7 col-lg-5">
          <div class="tarjeta tarjeta-form">
            <div class="text-center mb-4">
              <span class="marca-icono marca-icono-lg"><i class="bi bi-controller"></i></span>
              <h1 class="h3 mt-3">Iniciar sesión</h1>
              <p class="text-secundario mb-0">Volvé a la arena</p>
            </div>
            <div data-aviso></div>
            <form id="formLogin" novalidate>
              <div class="mb-3">
                <label class="form-label" for="identificador">Usuario o correo electrónico</label>
                <input class="form-control" id="identificador" name="identificador" required
                       autocomplete="username" autofocus>
              </div>
              <div class="mb-3">
                <label class="form-label" for="password">Contraseña</label>
                <input class="form-control" type="password" id="password" name="password" required
                       autocomplete="current-password">
              </div>
              <button class="btn btn-rojo w-100" type="submit">
                <i class="bi bi-box-arrow-in-right"></i> Entrar
              </button>
            </form>
            <p class="text-center text-secundario small mt-4 mb-0">
              ¿No tenés cuenta? <a class="enlace-rojo" href="#/registro">Creá una gratis</a>
            </p>
          </div>
        </div>
      </div>
    </div>`;

  const formulario = contenedor.querySelector("#formLogin");
  const aviso = contenedor.querySelector("[data-aviso]");

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    aviso.innerHTML = "";
    const boton = formulario.querySelector("button[type=submit]");
    boton.disabled = true;
    boton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Entrando…';

    try {
      const datos = new FormData(formulario);
      await iniciarSesion(datos.get("identificador"), datos.get("password"));
      toast("Sesión iniciada. ¡A jugar!", { titulo: "Bienvenido", tipo: "resultado" });
      window.location.hash = `#${destinoSeguro(query)}`;
    } catch (error) {
      marcarErrores(formulario, error.errores || {});
      aviso.innerHTML = `<div class="alert alert-danger">${resumenErrores(error)
        .map((mensaje) => `<div>${escapar(mensaje)}</div>`)
        .join("")}</div>`;
      boton.disabled = false;
      boton.innerHTML = '<i class="bi bi-box-arrow-in-right"></i> Entrar';
      if (error.status === 0) toast(mensajeError(error), { titulo: "Sin conexión", tipo: "disputa" });
    }
  });
}
