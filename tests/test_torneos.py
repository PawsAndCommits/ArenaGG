"""Pruebas del contrato HTTP de torneos."""
from datetime import datetime, timedelta

import pytest

from tests.ayudas import crear_torneo


def _fecha(dias: int = 3) -> str:
    return (datetime.now() + timedelta(days=dias)).replace(microsecond=0).isoformat()


def test_crear_torneo_requiere_sesion(client):
    respuesta = client.post(
        "/torneos",
        json={"nombre": "Sin sesión", "videojuego": "Valorant", "fecha": _fecha()},
    )
    assert respuesta.status_code == 401


def test_crear_torneo_como_jugador(client, jugador):
    respuesta = client.post(
        "/torneos",
        json={"nombre": "Copa del jugador", "videojuego": "Valorant", "fecha": _fecha()},
        headers=jugador["headers"],
    )
    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    assert datos["creado_por_id"] == jugador["id"]
    assert datos["creado_por"] == jugador["username"]
    assert datos["puede_gestionar"] is True
    assert datos["es_organizador"] is True


def test_crear_torneo_con_todos_los_campos(client, admin):
    respuesta = client.post(
        "/torneos",
        json={
            "nombre": "Valorant Masters",
            "descripcion": "Copa principal",
            "videojuego": "Valorant",
            "fecha": _fecha(10),
            "cupo_maximo": 16,
            "estado": "inscripciones_abiertas",
            "modalidad": "equipos",
            "jugadores_por_equipo": 5,
            "formato": "BO3",
            "destacado": True,
            "premio": "Trofeo",
            "reglas": "Fair play",
        },
        headers=admin["headers"],
    )
    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    assert datos["nombre"] == "Valorant Masters"
    assert datos["modalidad"] == "equipos"
    assert datos["modalidad_texto"] == "Por equipos"
    assert datos["formato"] == "BO3"
    assert datos["jugadores_por_equipo"] == 5
    assert datos["cupo_maximo"] == 16
    assert datos["inscriptos"] == 0
    assert datos["cupos_disponibles"] == 16
    assert datos["acepta_inscripciones"] is True
    assert datos["creado_por"] == "admin"
    assert datos["destacado"] is True
    assert datos["tiene_partidas"] is False


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"nombre": ""}, "nombre"),
        ({"videojuego": ""}, "videojuego"),
        ({"fecha": "no-es-fecha"}, "fecha"),
        ({"fecha": (datetime.now() - timedelta(days=1)).isoformat()}, "fecha"),
        ({"cupo_maximo": 1}, "cupo_maximo"),
        ({"formato": "BO7"}, "formato"),
        ({"modalidad": "duplas"}, "modalidad"),
        (
            {
                "modalidad": "equipos",
                "jugadores_por_equipo": None,
            },
            "jugadores_por_equipo",
        ),
    ],
)
def test_crear_torneo_valida_datos(client, admin, cambios, campo):
    respuesta = client.post(
        "/torneos",
        json={
            "nombre": "Copa válida",
            "videojuego": "Valorant",
            "fecha": _fecha(),
            "cupo_maximo": 8,
            **cambios,
        },
        headers=admin["headers"],
    )
    assert respuesta.status_code in (400, 422), respuesta.text
    assert campo in respuesta.json()["errores"]


def test_listado_filtros_y_videojuegos(client, admin):
    torneo_a = crear_torneo(
        client, admin["headers"], nombre="Alpha Cup", videojuego="Valorant"
    )
    torneo_b = crear_torneo(
        client,
        admin["headers"],
        nombre="Beta League",
        videojuego="Rocket League",
        modalidad="equipos",
        jugadores_por_equipo=2,
    )
    torneo_c = crear_torneo(
        client,
        admin["headers"],
        nombre="Gamma Open",
        videojuego="Valorant",
        estado="proximamente",
    )

    todos = client.get("/torneos").json()
    assert {torneo["id"] for torneo in todos} == {
        torneo_a["id"],
        torneo_b["id"],
        torneo_c["id"],
    }

    por_juego = client.get("/torneos", params={"videojuego": "rocket"}).json()
    assert [torneo["id"] for torneo in por_juego] == [torneo_b["id"]]

    por_estado = client.get(
        "/torneos", params={"estado": "proximamente"}
    ).json()
    assert [torneo["id"] for torneo in por_estado] == [torneo_c["id"]]

    por_modalidad = client.get(
        "/torneos", params={"modalidad": "equipos"}
    ).json()
    assert [torneo["id"] for torneo in por_modalidad] == [torneo_b["id"]]

    por_texto = client.get("/torneos", params={"q": "gamma"}).json()
    assert [torneo["id"] for torneo in por_texto] == [torneo_c["id"]]

    juegos = client.get("/videojuegos").json()
    assert juegos == ["Rocket League", "Valorant"]

    invalido = client.get("/torneos", params={"estado": "inexistente"})
    assert invalido.status_code == 400


def test_detalle_participantes_y_actualizacion(client, admin, jugador):
    torneo = crear_torneo(
        client,
        admin["headers"],
        nombre="Copa editable",
        reglas="Reglas originales",
        premio="Premio original",
    )
    detalle = client.get(f"/torneos/{torneo['id']}")
    assert detalle.status_code == 200
    assert detalle.json()["reglas"] == "Reglas originales"

    actualizado = client.put(
        f"/torneos/{torneo['id']}",
        json={
            "nombre": "Copa actualizada",
            "premio": "Nuevo premio",
            "cupo_maximo": 12,
        },
        headers=admin["headers"],
    )
    assert actualizado.status_code == 200, actualizado.text
    assert actualizado.json()["nombre"] == "Copa actualizada"
    assert actualizado.json()["premio"] == "Nuevo premio"
    assert actualizado.json()["cupo_maximo"] == 12

    participantes = client.get(f"/torneos/{torneo['id']}/participantes")
    assert participantes.status_code == 200
    assert participantes.json()["torneo_id"] == torneo["id"]
    assert participantes.json()["inscriptos"] == 0
    assert participantes.json()["participantes"] == []

    no_admin = client.put(
        f"/torneos/{torneo['id']}",
        json={"nombre": "Intento"},
        headers=jugador["headers"],
    )
    assert no_admin.status_code == 403


def test_no_se_pueden_forzar_estados_del_sistema(client, admin):
    torneo = crear_torneo(client, admin["headers"])
    for estado in ("en_curso", "finalizado"):
        respuesta = client.put(
            f"/torneos/{torneo['id']}",
            json={"estado": estado},
            headers=admin["headers"],
        )
        assert respuesta.status_code == 400
        assert "estado" in respuesta.json()["errores"]


def test_eliminar_torneo(client, admin, jugador):
    torneo = crear_torneo(client, admin["headers"])
    no_admin = client.delete(
        f"/torneos/{torneo['id']}", headers=jugador["headers"]
    )
    assert no_admin.status_code == 403

    eliminado = client.delete(
        f"/torneos/{torneo['id']}", headers=admin["headers"]
    )
    assert eliminado.status_code == 200
    assert eliminado.json()["mensaje"] == "Torneo eliminado."
    assert client.get(f"/torneos/{torneo['id']}").status_code == 404


def test_torneo_inexistente(client):
    assert client.get("/torneos/999").status_code == 404
    assert client.get("/torneos/999/participantes").status_code == 404
    assert client.get("/torneos/999/partidas").status_code == 404
