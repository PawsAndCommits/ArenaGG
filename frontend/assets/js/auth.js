import { api, configurarApi } from "./api.js";

const CLAVE_TOKEN = "arenagg.token";
const CLAVE_USUARIO = "arenagg.usuario";

function leerToken() {
  try {
    return localStorage.getItem(CLAVE_TOKEN);
  } catch (_error) {
    return null;
  }
}

function leerUsuario() {
  try {
    const guardado = localStorage.getItem(CLAVE_USUARIO);
    return guardado ? JSON.parse(guardado) : null;
  } catch (_error) {
    return null;
  }
}

let token = leerToken();
let usuario = leerUsuario();

function guardar() {
  try {
    if (token) localStorage.setItem(CLAVE_TOKEN, token);
    else localStorage.removeItem(CLAVE_TOKEN);
    if (usuario) localStorage.setItem(CLAVE_USUARIO, JSON.stringify(usuario));
    else localStorage.removeItem(CLAVE_USUARIO);
  } catch (_error) {
    // El almacenamiento puede estar bloqueado; la sesión sigue en memoria.
  }
}

function emitir(motivo) {
  window.dispatchEvent(
    new CustomEvent("arenagg:sesion", {
      detail: { autenticado: Boolean(token && usuario), usuario, motivo },
    })
  );
}

export function tokenActual() {
  return token;
}

export function usuarioActual() {
  return usuario;
}

export function estaAutenticado() {
  return Boolean(token && usuario);
}

export function esAdmin() {
  return Boolean(usuario && usuario.rol === "admin");
}

export function iniciarSesion(identificador, password) {
  return api.login(identificador, password).then((respuesta) => {
    token = respuesta.access_token;
    usuario = respuesta.usuario;
    guardar();
    emitir("login");
    return respuesta;
  });
}

export function registrar(datos) {
  return api.post("/auth/registro", datos, { autenticado: false }).then((respuesta) => {
    token = respuesta.access_token;
    usuario = respuesta.usuario;
    guardar();
    emitir("registro");
    return respuesta;
  });
}

export function cerrarSesion({ motivo = "manual" } = {}) {
  token = null;
  usuario = null;
  guardar();
  emitir(motivo);
}

export function actualizarUsuario(nuevo) {
  usuario = nuevo;
  guardar();
  emitir("perfil");
}

export async function refrescarSesion() {
  if (!token) {
    usuario = null;
    guardar();
    return null;
  }
  try {
    usuario = await api.get("/auth/me");
    guardar();
    emitir("refresco");
    return usuario;
  } catch (error) {
    if (error.status === 401) {
      cerrarSesion({ motivo: "expirada" });
    }
    return usuario;
  }
}

configurarApi({
  token: tokenActual,
  noAutorizado(error) {
    if (!token) return;
    cerrarSesion({ motivo: "expirada" });
    window.dispatchEvent(
      new CustomEvent("arenagg:aviso", { detail: { mensaje: error.detalle } })
    );
  },
});

window.addEventListener("storage", (evento) => {
  if (evento.key !== CLAVE_TOKEN && evento.key !== CLAVE_USUARIO) return;
  token = leerToken();
  usuario = leerUsuario();
  emitir("otra-pestana");
});
