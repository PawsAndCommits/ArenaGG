const BASE = "";

let obtenerToken = () => null;
let alNoAutorizado = () => {};

export class ApiError extends Error {
  constructor(status, detalle, errores = {}) {
    super(detalle);
    this.name = "ApiError";
    this.status = status;
    this.detalle = detalle;
    this.errores = errores || {};
  }
}

export function configurarApi({ token, noAutorizado } = {}) {
  if (typeof token === "function") obtenerToken = token;
  if (typeof noAutorizado === "function") alNoAutorizado = noAutorizado;
}

async function solicitar(ruta, opciones = {}) {
  const {
    metodo = "GET",
    cuerpo,
    formulario = false,
    autenticado = true,
    cabeceras = {},
  } = opciones;

  const headers = { Accept: "application/json", ...cabeceras };
  const token = autenticado ? obtenerToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  const configuracion = { method: metodo, headers };

  if (cuerpo !== undefined && cuerpo !== null) {
    if (formulario) {
      const datos = new URLSearchParams();
      Object.entries(cuerpo).forEach(([clave, valor]) => {
        if (valor !== undefined && valor !== null) datos.append(clave, valor);
      });
      headers["Content-Type"] = "application/x-www-form-urlencoded";
      configuracion.body = datos.toString();
    } else if (cuerpo instanceof FormData) {
      configuracion.body = cuerpo;
    } else {
      headers["Content-Type"] = "application/json";
      configuracion.body = JSON.stringify(cuerpo);
    }
  }

  let respuesta;
  try {
    respuesta = await fetch(`${BASE}${ruta}`, configuracion);
  } catch (_error) {
    throw new ApiError(0, "No se pudo conectar con el servidor. Revisá tu conexión.");
  }

  const texto = await respuesta.text();
  let datos = null;
  if (texto) {
    try {
      datos = JSON.parse(texto);
    } catch (_error) {
      datos = texto;
    }
  }

  if (!respuesta.ok) {
    const detalle =
      (datos && typeof datos === "object" && datos.detail) ||
      (typeof datos === "string" && datos) ||
      `Error ${respuesta.status}.`;
    const errores =
      datos && typeof datos === "object" && datos.errores ? datos.errores : {};
    const error = new ApiError(respuesta.status, detalle, errores);
    if (respuesta.status === 401 && autenticado) alNoAutorizado(error);
    throw error;
  }

  return datos;
}

function conQuery(ruta, query) {
  if (!query) return ruta;
  const parametros = new URLSearchParams();
  Object.entries(query).forEach(([clave, valor]) => {
    if (valor !== undefined && valor !== null && valor !== "") {
      parametros.append(clave, valor);
    }
  });
  const cadena = parametros.toString();
  return cadena ? `${ruta}?${cadena}` : ruta;
}

export const api = {
  get(ruta, query, opciones = {}) {
    return solicitar(conQuery(ruta, query), opciones);
  },
  post(ruta, cuerpo, opciones = {}) {
    return solicitar(ruta, { ...opciones, metodo: "POST", cuerpo });
  },
  put(ruta, cuerpo, opciones = {}) {
    return solicitar(ruta, { ...opciones, metodo: "PUT", cuerpo });
  },
  delete(ruta, opciones = {}) {
    return solicitar(ruta, { ...opciones, metodo: "DELETE" });
  },
  login(usuario, password) {
    return solicitar("/auth/login", {
      metodo: "POST",
      formulario: true,
      autenticado: false,
      cuerpo: { username: usuario, password },
    });
  },
};
