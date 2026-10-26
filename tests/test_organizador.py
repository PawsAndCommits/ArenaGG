"""Pruebas de permisos del organizador de cada torneo."""
from datetime import datetime, timedelta

from tests.ayudas import (
    crear_jugadores,
    crear_torneo,
    inscribir,
    partida_jugable,
    partidas,
)


def _fecha(dias: int = 3) -> str:
    return (datetime.now() + timedelta(days=dias)).replace(microsecond=0).isoformat()


def _preparar_torneo(client, organizador, jugadores, **cambios):
    torneo = crear_torneo(client, organizador["headers"], **cambios)
    for jugador in jugadores:
        inscribir(client, jugador["headers"], torneo["id"])
    respuesta = client.patch(
        f"/torneos/{torneo['id']}/iniciar", headers=organizador["headers"]
    )
    assert respuesta.status_code == 200, respuesta.text
    return torneo


def test_organizador_crea_y_gestiona_su_torneo(client, jugador):
    respuesta = client.post(
        "/torneos",
        json={
            "nombre": "Copa del organizador",
            "descripcion": "Creada por un jugador",
            "videojuego": "Valorant",
            "fecha": _fecha(),
            "cupo_maximo": 8,
            "formato": "BO1",
        },
        headers=jugador["headers"],
    )
    assert respuesta.status_code == 201, respuesta.text
    torneo = respuesta.json()
    assert torneo["creado_por_id"] == jugador["id"]
    assert torneo["puede_gestionar"] is True
    assert torneo["es_organizador"] is True

    actualizado = client.put(
        f"/torneos/{torneo['id']}",
        json={"nombre": "Copa renombrada", "premio": "Trofeo"},
        headers=jugador["headers"],
    )
    assert actualizado.status_code == 200, actualizado.text
    assert actualizado.json()["nombre"] == "Copa renombrada"
    assert actualizado.json()["premio"] == "Trofeo"
    assert actualizado.json()["puede_gestionar"] is True


def test_mis_torneos_solo_muestra_los_propios(client, jugador, crear_usuario, autenticar):
    otro = crear_usuario("otro-organizador")
    otro["headers"] = autenticar(otro["username"])

    propio_a = crear_torneo(client, jugador["headers"], nombre="Propio A")
    propio_b = crear_torneo(client, jugador["headers"], nombre="Propio B")
    ajeno = crear_torneo(client, otro["headers"], nombre="Ajeno")

    mios = client.get("/torneos/mios", headers=jugador["headers"])
    assert mios.status_code == 200
    assert {torneo["id"] for torneo in mios.json()} == {
        propio_a["id"],
        propio_b["id"],
    }
    assert all(torneo["es_organizador"] for torneo in mios.json())

    del_otro = client.get("/torneos/mios", headers=otro["headers"])
    assert [torneo["id"] for torneo in del_otro.json()] == [ajeno["id"]]

    assert client.get("/torneos/mios").status_code == 401


def test_solo_el_organizador_o_un_admin_gestiona(
    client, jugador, crear_usuario, autenticar, admin
):
    intruso = crear_usuario("intruso")
    intruso["headers"] = autenticar(intruso["username"])
    torneo = crear_torneo(client, jugador["headers"], nombre="Copa privada")

    assert (
        client.put(
            f"/torneos/{torneo['id']}",
            json={"nombre": "Intento ajeno"},
            headers=intruso["headers"],
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/torneos/{torneo['id']}", headers=intruso["headers"]
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/torneos/{torneo['id']}/iniciar", headers=intruso["headers"]
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/torneos/{torneo['id']}/reiniciar", headers=intruso["headers"]
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/torneos/{torneo['id']}/finalizar", headers=intruso["headers"]
        ).status_code
        == 403
    )

    ajeno = client.get(f"/torneos/{torneo['id']}", headers=intruso["headers"])
    assert ajeno.json()["puede_gestionar"] is False
    assert ajeno.json()["es_organizador"] is False

    como_admin = client.put(
        f"/torneos/{torneo['id']}",
        json={"premio": "Premio del admin"},
        headers=admin["headers"],
    )
    assert como_admin.status_code == 200, como_admin.text
    assert como_admin.json()["puede_gestionar"] is True
    assert como_admin.json()["es_organizador"] is False


def test_organizador_no_puede_inscribirse_en_su_torneo(client, jugador):
    torneo = crear_torneo(client, jugador["headers"], nombre="Copa propia")
    respuesta = client.post(
        f"/torneos/{torneo['id']}/inscribirse", headers=jugador["headers"]
    )
    assert respuesta.status_code == 403
    assert "organizador" in respuesta.json()["detail"].lower()


def test_finalizacion_manual_del_organizador(
    client, jugador, crear_usuario, autenticar
):
    jugadores = crear_jugadores(crear_usuario, autenticar, 2, prefijo="final")
    torneo = _preparar_torneo(client, jugador, jugadores, nombre="Copa a finalizar")

    respuesta = client.post(
        f"/torneos/{torneo['id']}/finalizar", headers=jugador["headers"]
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "finalizado"

    repetida = client.post(
        f"/torneos/{torneo['id']}/finalizar", headers=jugador["headers"]
    )
    assert repetida.status_code == 409


def test_finalizar_bloquea_resultados_sin_confirmar(
    client, jugador, crear_usuario, autenticar
):
    jugadores = crear_jugadores(crear_usuario, autenticar, 2, prefijo="pendiente")
    torneo = _preparar_torneo(client, jugador, jugadores, nombre="Copa pendiente")

    partida = partida_jugable(partidas(client, torneo["id"]))
    assert partida
    reporte = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/resultado",
        json={"puntaje1": 1, "puntaje2": 0},
        headers=jugadores[0]["headers"],
    )
    assert reporte.status_code == 200, reporte.text

    bloqueada = client.post(
        f"/torneos/{torneo['id']}/finalizar", headers=jugador["headers"]
    )
    assert bloqueada.status_code == 409

    resuelta = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/resolver",
        json={"puntaje1": 1, "puntaje2": 0},
        headers=jugador["headers"],
    )
    assert resuelta.status_code == 200, resuelta.text
    final = client.get(f"/torneos/{torneo['id']}")
    assert final.json()["estado"] == "finalizado"


def test_organizador_resuelve_disputa_y_programa(
    client, jugador, crear_usuario, autenticar
):
    jugadores = crear_jugadores(crear_usuario, autenticar, 3, prefijo="disputa")
    torneo = _preparar_torneo(client, jugador, jugadores[:2], nombre="Copa disputa")
    partida = partida_jugable(partidas(client, torneo["id"]))
    assert partida

    programada = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/programar",
        json={"fecha_programada": _fecha(1)},
        headers=jugador["headers"],
    )
    assert programada.status_code == 200, programada.text

    ajeno = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/programar",
        json={"fecha_programada": _fecha(2)},
        headers=jugadores[2]["headers"],
    )
    assert ajeno.status_code == 403

    reporte = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/resultado",
        json={"puntaje1": 1, "puntaje2": 0},
        headers=jugadores[0]["headers"],
    )
    assert reporte.status_code == 200, reporte.text

    disputa = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/disputar",
        json={"motivo": "El marcador no coincide"},
        headers=jugadores[1]["headers"],
    )
    assert disputa.status_code == 200, disputa.text

    intento_ajeno = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/resolver",
        json={"puntaje1": 1, "puntaje2": 0},
        headers=jugadores[2]["headers"],
    )
    assert intento_ajeno.status_code == 403

    resuelta = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/resolver",
        json={"puntaje1": 1, "puntaje2": 0},
        headers=jugador["headers"],
    )
    assert resuelta.status_code == 200, resuelta.text
    assert resuelta.json()["resultado"]["estado"] == "confirmado"


def test_organizador_elimina_inscripcion_de_su_torneo(
    client, jugador, crear_usuario, autenticar
):
    jugadores = crear_jugadores(crear_usuario, autenticar, 2, prefijo="baja")
    torneo = crear_torneo(client, jugador["headers"], nombre="Copa bajas")
    inscripcion = inscribir(client, jugadores[0]["headers"], torneo["id"])

    ajeno = client.delete(
        f"/inscripciones/{inscripcion['id']}", headers=jugadores[1]["headers"]
    )
    assert ajeno.status_code == 403

    eliminada = client.delete(
        f"/inscripciones/{inscripcion['id']}", headers=jugador["headers"]
    )
    assert eliminada.status_code == 204
    assert eliminada.content == b""

    participantes = client.get(f"/torneos/{torneo['id']}/participantes").json()
    assert participantes["participantes"] == []


def test_destacado_sigue_siendo_solo_de_administradores(
    client, jugador, admin
):
    rechazado = client.post(
        "/torneos",
        json={
            "nombre": "Copa destacada",
            "videojuego": "Valorant",
            "fecha": _fecha(),
            "destacado": True,
        },
        headers=jugador["headers"],
    )
    assert rechazado.status_code == 403

    torneo = crear_torneo(client, jugador["headers"], nombre="Copa normal")
    aprobado = client.put(
        f"/torneos/{torneo['id']}",
        json={"destacado": True},
        headers=admin["headers"],
    )
    assert aprobado.status_code == 200, aprobado.text
    assert aprobado.json()["destacado"] is True

    bloqueado = client.put(
        f"/torneos/{torneo['id']}",
        json={"destacado": False},
        headers=jugador["headers"],
    )
    assert bloqueado.status_code == 403

    permitido = client.put(
        f"/torneos/{torneo['id']}",
        json={"premio": "Premio nuevo"},
        headers=jugador["headers"],
    )
    assert permitido.status_code == 200, permitido.text
    assert permitido.json()["destacado"] is True
