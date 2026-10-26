import { errorPagina } from "../components.js";

export async function render(contenedor) {
  contenedor.innerHTML = errorPagina(
    "404",
    "La página que buscás no existe o cambió de lugar."
  );
}
