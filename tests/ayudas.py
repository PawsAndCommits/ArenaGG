"""Utilidades compartidas por los casos de prueba."""
from datetime import datetime, timedelta

MARCADORES = {
    "BO1": (1, 0),
    "BO3": (2, 0),
    "BO5": (3, 0),
}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def crear_torneo(client, headers: dict, **cambios) -> dict:
    datos = {
        "nombre": "Copa de prueba",
        "descripcion": "Torneo de prueba",
        "videojuego": "Valorant",
        "fecha": (datetime.now() + timedelta(days=3)).replace(microsecond=0).isoformat(),
        "cupo_maximo": 8,
        "estado": "inscripciones_abiertas",
        "modalidad": "individual",
        "formato": "BO1",
    }
    datos.update(cambios)
    respuesta = client.post("/torneos", json=datos, headers=headers)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def inscribir(client, headers: dict, torneo_id: int, **datos) -> dict:
    opciones = {"headers": headers}
    if datos:
        opciones["json"] = datos
    respuesta = client.post(f"/torneos/{torneo_id}/inscribirse", **opciones)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def partidas(client, torneo_id: int, headers: dict | None = None) -> list[dict]:
    respuesta = client.get(
        f"/torneos/{torneo_id}/partidas", headers=headers or {}
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["partidas"]


def partida_jugable(lista: list[dict]) -> dict | None:
    return next(
        (
            partida
            for partida in lista
            if partida["estado"] == "pendiente"
            and partida["lista_para_jugar"]
            and not partida["resultado"]
        ),
        None,
    )


def crear_jugadores(crear_usuario, autenticar, cantidad: int, prefijo: str = "jugador"):
    jugadores = []
    for indice in range(1, cantidad + 1):
        jugador = crear_usuario(f"{prefijo}{indice}")
        jugador["headers"] = autenticar(jugador["username"])
        jugadores.append(jugador)
    return jugadores


def disputar_llave(client, torneo_id: int, jugadores: list[dict], formato: str = "BO1"):
    """Juega y confirma todas las partidas posibles, ronda por ronda."""
    headers_por_id = {jugador["id"]: jugador["headers"] for jugador in jugadores}
    marcador = MARCADORES[formato]

    for _ in range(64):
        partida = partida_jugable(partidas(client, torneo_id))
        if not partida:
            return partidas(client, torneo_id)

        capitan1 = partida["participante1"]["capitan_id"]
        capitan2 = partida["participante2"]["capitan_id"]
        assert capitan1 in headers_por_id
        assert capitan2 in headers_por_id

        respuesta = client.post(
            f"/torneos/{torneo_id}/partidas/{partida['id']}/resultado",
            json={"puntaje1": marcador[0], "puntaje2": marcador[1]},
            headers=headers_por_id[capitan1],
        )
        assert respuesta.status_code == 200, respuesta.text

        respuesta = client.post(
            f"/torneos/{torneo_id}/partidas/{partida['id']}/confirmar",
            headers=headers_por_id[capitan2],
        )
        assert respuesta.status_code == 200, respuesta.text

    raise AssertionError("La llave no terminó en la cantidad de pasos esperada.")
