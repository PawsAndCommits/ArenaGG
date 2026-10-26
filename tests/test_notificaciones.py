"""Pruebas de la bandeja de notificaciones y el polling."""
from tests.ayudas import crear_torneo, inscribir


def _generar_notificaciones(client, admin, jugador, cantidad=3):
    for indice in range(1, cantidad + 1):
        torneo = crear_torneo(
            client,
            admin["headers"],
            nombre=f"Copa de avisos {indice}",
            videojuego="Valorant",
        )
        inscribir(client, jugador["headers"], torneo["id"])


def test_resumen_y_bandeja(client, admin, jugador):
    _generar_notificaciones(client, admin, jugador)

    resumen = client.get("/notificaciones/resumen", headers=jugador["headers"])
    assert resumen.status_code == 200
    assert resumen.json()["sin_leer"] == 3
    assert len(resumen.json()["recientes"]) == 3
    assert all(item["leida"] is False for item in resumen.json()["recientes"])
    assert all(item["url"].startswith("#/torneos/") for item in resumen.json()["recientes"])

    bandeja = client.get("/notificaciones", headers=jugador["headers"])
    assert bandeja.status_code == 200
    datos = bandeja.json()
    assert datos["total"] == 3
    assert datos["pagina"] == 1
    assert datos["paginas"] == 1
    assert datos["sin_leer"] == 3
    assert len(datos["items"]) == 3
    assert {item["tipo"] for item in datos["items"]} == {"inscripcion"}


def test_paginacion_y_filtros(client, admin, jugador):
    _generar_notificaciones(client, admin, jugador)

    pagina_1 = client.get(
        "/notificaciones",
        params={"pagina": 1, "por_pagina": 2},
        headers=jugador["headers"],
    ).json()
    assert pagina_1["paginas"] == 2
    assert len(pagina_1["items"]) == 2

    pagina_2 = client.get(
        "/notificaciones",
        params={"pagina": 2, "por_pagina": 2},
        headers=jugador["headers"],
    ).json()
    assert len(pagina_2["items"]) == 1

    sin_leer = client.get(
        "/notificaciones", params={"filtro": "sin_leer"}, headers=jugador["headers"]
    ).json()
    assert sin_leer["total"] == 3

    primero = pagina_1["items"][0]
    leida = client.post(
        f"/notificaciones/{primero['id']}/leer", headers=jugador["headers"]
    )
    assert leida.status_code == 200
    assert leida.json()["sin_leer"] == 2
    assert leida.json()["notificacion"]["leida"] is True

    restantes = client.get(
        "/notificaciones", params={"filtro": "sin_leer"}, headers=jugador["headers"]
    ).json()
    assert restantes["total"] == 2

    repetida = client.post(
        f"/notificaciones/{primero['id']}/leer", headers=jugador["headers"]
    )
    assert repetida.status_code == 200
    assert repetida.json()["sin_leer"] == 2


def test_marcar_todas_y_polling(client, admin, jugador):
    _generar_notificaciones(client, admin, jugador, cantidad=2)

    todas = client.post(
        "/notificaciones/leer-todas", headers=jugador["headers"]
    )
    assert todas.status_code == 200
    assert todas.json()["mensaje"] == "Notificaciones marcadas como leídas."

    resumen = client.get(
        "/notificaciones/resumen", headers=jugador["headers"]
    ).json()
    assert resumen["sin_leer"] == 0
    assert resumen["recientes"] == []

    bandeja = client.get("/notificaciones", headers=jugador["headers"]).json()
    assert bandeja["total"] == 2
    assert all(item["leida"] is True for item in bandeja["items"])


def test_no_se_puede_leer_una_notificacion_ajena(client, admin, jugador, crear_usuario, autenticar):
    _generar_notificaciones(client, admin, jugador, cantidad=1)
    ajena = client.get("/notificaciones", headers=jugador["headers"]).json()["items"][0]

    intruso = crear_usuario("intruso")
    headers = autenticar(intruso["username"])
    respuesta = client.post(
        f"/notificaciones/{ajena['id']}/leer", headers=headers
    )
    assert respuesta.status_code == 403

    inexistente = client.post("/notificaciones/999/leer", headers=headers)
    assert inexistente.status_code == 404


def test_notificaciones_requieren_sesion_y_parametros_validos(client):
    assert client.get("/notificaciones").status_code == 401
    assert client.get("/notificaciones/resumen").status_code == 401


def test_parametros_de_consulta_invalidos(client, jugador):
    filtro = client.get(
        "/notificaciones", params={"filtro": "otro"}, headers=jugador["headers"]
    )
    assert filtro.status_code == 422

    pagina = client.get(
        "/notificaciones", params={"pagina": 0}, headers=jugador["headers"]
    )
    assert pagina.status_code == 422

    tamano = client.get(
        "/notificaciones", params={"por_pagina": 0}, headers=jugador["headers"]
    )
    assert tamano.status_code == 422
