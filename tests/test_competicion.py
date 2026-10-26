"""Pruebas de inscripciones, llaves, resultados y posiciones."""
from datetime import datetime, timedelta

from tests.ayudas import (
    crear_jugadores,
    crear_torneo,
    disputar_llave,
    inscribir,
    partida_jugable,
    partidas,
)


def _inscribir_jugadores(client, torneo_id, jugadores):
    for jugador in jugadores:
        inscribir(client, jugador["headers"], torneo_id)


def _iniciar(client, admin, torneo_id):
    respuesta = client.post(
        f"/torneos/{torneo_id}/iniciar", headers=admin["headers"]
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_torneo_completo_con_confirmaciones(client, admin, crear_usuario, autenticar):
    jugadores = crear_jugadores(crear_usuario, autenticar, 4)
    torneo = crear_torneo(
        client, admin["headers"], nombre="Copa completa", formato="BO3"
    )
    _inscribir_jugadores(client, torneo["id"], jugadores)

    doble = client.post(
        f"/torneos/{torneo['id']}/inscribirse", headers=jugadores[0]["headers"]
    )
    assert doble.status_code == 409

    datos = _iniciar(client, admin, torneo["id"])
    assert datos["estado"] == "en_curso"
    assert datos["total_rondas"] == 2
    assert datos["tiene_partidas"] is True

    llave = partidas(client, torneo["id"])
    assert len(llave) == 3
    assert sum(partida["ronda"] == 1 for partida in llave) == 2
    assert sum(partida["ronda"] == 2 for partida in llave) == 1
    assert all(partida["estado"] != "bye" for partida in llave)

    primera = partida_jugable(llave)
    fecha = (datetime.now() + timedelta(days=4)).replace(microsecond=0).isoformat()
    programada = client.post(
        f"/torneos/{torneo['id']}/partidas/{primera['id']}/programar",
        json={"fecha_programada": fecha},
        headers=admin["headers"],
    )
    assert programada.status_code == 200
    assert programada.json()["fecha_programada"].startswith(fecha[:16])

    finalizadas = disputar_llave(
        client, torneo["id"], jugadores, formato="BO3"
    )
    final = next(partida for partida in finalizadas if partida["ronda"] == 2)
    assert final["estado"] == "finalizada"
    assert final["resultado"]["estado"] == "confirmado"
    assert final["resultado"]["puntaje1"] == 2
    assert final["resultado"]["puntaje2"] == 0

    detalle = client.get(f"/torneos/{torneo['id']}").json()
    assert detalle["estado"] == "finalizado"
    assert detalle["campeon"] is not None
    assert detalle["campeon"]["id"] == final["ganador"]["inscripcion_id"]

    posiciones = client.get(f"/torneos/{torneo['id']}/posiciones").json()
    assert posiciones["posiciones"][0]["estado"] == "Campeón"
    assert posiciones["posiciones"][0]["victorias"] == 2
    assert posiciones["posiciones"][0]["partidas_jugadas"] == 2

    campeon = next(
        jugador
        for jugador in jugadores
        if jugador["id"] == detalle["campeon"]["usuario"]["id"]
    )
    resumen = client.get(
        "/notificaciones/resumen", headers=campeon["headers"]
    ).json()
    assert resumen["sin_leer"] >= 1
    assert any(item["tipo"] == "campeon" for item in resumen["recientes"])

    historial = client.get(f"/usuarios/{campeon['id']}/historial").json()
    assert historial["historial"][0]["torneo"]["estado"] == "finalizado"


def test_disputa_y_resolucion_del_admin(client, admin, crear_usuario, autenticar):
    jugadores = crear_jugadores(crear_usuario, autenticar, 2, prefijo="duelo")
    torneo = crear_torneo(client, admin["headers"], nombre="Copa disputa")
    _inscribir_jugadores(client, torneo["id"], jugadores)
    _iniciar(client, admin, torneo["id"])

    partida = partida_jugable(partidas(client, torneo["id"]))
    assert partida is not None
    primero = partida["participante1"]["capitan_id"]
    segundo = partida["participante2"]["capitan_id"]
    headers = {jugador["id"]: jugador["headers"] for jugador in jugadores}

    cargado = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/resultado",
        json={"puntaje1": 1, "puntaje2": 0},
        headers=headers[primero],
    )
    assert cargado.status_code == 200
    assert cargado.json()["resultado"]["estado"] == "pendiente"
    assert cargado.json()["estado_texto"] == "Esperando confirmación"

    disputa = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/disputar",
        json={"motivo": "El marcador cargado no coincide con la partida."},
        headers=headers[segundo],
    )
    assert disputa.status_code == 200
    assert disputa.json()["resultado"]["estado"] == "disputa"
    assert disputa.json()["estado_texto"] == "En disputa"

    aviso_admin = client.get(
        "/notificaciones/resumen", headers=admin["headers"]
    ).json()
    assert any(item["tipo"] == "disputa" for item in aviso_admin["recientes"])

    resuelto = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/resolver",
        json={"puntaje1": 0, "puntaje2": 1},
        headers=admin["headers"],
    )
    assert resuelto.status_code == 200, resuelto.text
    assert resuelto.json()["estado"] == "finalizada"
    assert resuelto.json()["resultado"]["estado"] == "confirmado"
    assert resuelto.json()["ganador"]["usuario_id"] == segundo

    detalle = client.get(f"/torneos/{torneo['id']}").json()
    assert detalle["estado"] == "finalizado"


def test_resultado_rechazado_se_puede_volver_a_cargar(client, admin, crear_usuario, autenticar):
    jugadores = crear_jugadores(crear_usuario, autenticar, 2, prefijo="rechazo")
    torneo = crear_torneo(client, admin["headers"], nombre="Copa rechazo")
    _inscribir_jugadores(client, torneo["id"], jugadores)
    _iniciar(client, admin, torneo["id"])

    partida = partida_jugable(partidas(client, torneo["id"]))
    headers = {jugador["id"]: jugador["headers"] for jugador in jugadores}
    primero = partida["participante1"]["capitan_id"]

    assert client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/resultado",
        json={"puntaje1": 1, "puntaje2": 0},
        headers=headers[primero],
    ).status_code == 200

    rechazado = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/rechazar",
        headers=admin["headers"],
    )
    assert rechazado.status_code == 200
    assert rechazado.json()["estado"] == "pendiente"
    assert rechazado.json()["resultado"] is None

    nuevo = client.post(
        f"/torneos/{torneo['id']}/partidas/{partida['id']}/resultado",
        json={"puntaje1": 1, "puntaje2": 0},
        headers=headers[primero],
    )
    assert nuevo.status_code == 200


def test_marcador_respeta_formato_y_participantes(client, admin, crear_usuario, autenticar):
    jugadores = crear_jugadores(crear_usuario, autenticar, 2, prefijo="marcador")
    torneo = crear_torneo(
        client, admin["headers"], nombre="Copa marcador", formato="BO3"
    )
    _inscribir_jugadores(client, torneo["id"], jugadores)
    _iniciar(client, admin, torneo["id"])

    partida = partida_jugable(partidas(client, torneo["id"]))
    primero = partida["participante1"]["capitan_id"]
    headers = {jugador["id"]: jugador["headers"] for jugador in jugadores}
    ruta = f"/torneos/{torneo['id']}/partidas/{partida['id']}/resultado"

    empate = client.post(
        ruta, json={"puntaje1": 1, "puntaje2": 1}, headers=headers[primero]
    )
    assert empate.status_code == 400
    assert "puntaje" in empate.json()["errores"]

    formato = client.post(
        ruta, json={"puntaje1": 1, "puntaje2": 0}, headers=headers[primero]
    )
    assert formato.status_code == 400
    assert "formato" in formato.json()["errores"]

    ajeno = crear_usuario("miron")
    ajeno_headers = autenticar("miron")
    sin_permiso = client.post(
        ruta, json={"puntaje1": 2, "puntaje2": 0}, headers=ajeno_headers
    )
    assert sin_permiso.status_code == 403


def test_pase_directo_con_tres_jugadores(client, admin, crear_usuario, autenticar):
    jugadores = crear_jugadores(crear_usuario, autenticar, 3, prefijo="bye")
    torneo = crear_torneo(client, admin["headers"], nombre="Copa con bye")
    _inscribir_jugadores(client, torneo["id"], jugadores)
    _iniciar(client, admin, torneo["id"])

    llave = partidas(client, torneo["id"])
    assert len(llave) == 3
    assert sum(partida["estado"] == "bye" for partida in llave) == 1
    final = next(partida for partida in llave if partida["ronda"] == 2)
    assert (final["participante1"] is None) != (final["participante2"] is None)

    finalizadas = disputar_llave(client, torneo["id"], jugadores)
    assert all(partida["estado"] in ("finalizada", "bye") for partida in finalizadas)
    detalle = client.get(f"/torneos/{torneo['id']}").json()
    assert detalle["estado"] == "finalizado"
    assert detalle["campeon"] is not None


def test_inscripciones_y_cupos(client, admin, crear_usuario, autenticar):
    jugadores = crear_jugadores(crear_usuario, autenticar, 3, prefijo="cupo")
    torneo = crear_torneo(
        client, admin["headers"], nombre="Copa de cupos", cupo_maximo=2
    )

    inscribir(client, jugadores[0]["headers"], torneo["id"])
    inscribir(client, jugadores[1]["headers"], torneo["id"])

    completo = client.post(
        f"/torneos/{torneo['id']}/inscribirse", headers=jugadores[2]["headers"]
    )
    assert completo.status_code == 409
    assert "completo" in completo.json()["detail"].lower()

    participantes = client.get(f"/torneos/{torneo['id']}/participantes").json()
    assert participantes["inscriptos"] == 2
    assert participantes["cupos_disponibles"] == 0
    assert len(participantes["participantes"]) == 2
    assert participantes["participantes"][0]["roster"][0]["username"] in {
        jugadores[0]["username"],
        jugadores[1]["username"],
    }


def test_cancelar_inscripcion_antes_y_despues_de_iniciar(client, admin, crear_usuario, autenticar):
    jugadores = crear_jugadores(crear_usuario, autenticar, 2, prefijo="baja")
    torneo = crear_torneo(client, admin["headers"], nombre="Copa de bajas")

    inscribir(client, jugadores[0]["headers"], torneo["id"])
    cancelada = client.delete(
        f"/torneos/{torneo['id']}/inscribirse", headers=jugadores[0]["headers"]
    )
    assert cancelada.status_code == 200
    assert client.get(f"/torneos/{torneo['id']}/participantes").json()["inscriptos"] == 0

    inscribir(client, jugadores[0]["headers"], torneo["id"])
    inscribir(client, jugadores[1]["headers"], torneo["id"])
    _iniciar(client, admin, torneo["id"])

    tarde = client.delete(
        f"/torneos/{torneo['id']}/inscribirse", headers=jugadores[0]["headers"]
    )
    assert tarde.status_code == 409


def test_iniciar_exige_dos_participantes(client, admin, crear_usuario, autenticar):
    jugador = crear_jugadores(crear_usuario, autenticar, 1, prefijo="solo")[0]
    torneo = crear_torneo(client, admin["headers"], nombre="Copa solitaria")
    inscribir(client, jugador["headers"], torneo["id"])

    respuesta = client.post(
        f"/torneos/{torneo['id']}/iniciar", headers=admin["headers"]
    )
    assert respuesta.status_code == 409
    assert "2 inscriptos" in respuesta.json()["detail"]


def test_no_se_puede_inscribir_ni_reiniciar_sin_permiso(client, admin, jugador, crear_usuario, autenticar):
    jugadores = crear_jugadores(crear_usuario, autenticar, 2, prefijo="orden")
    torneo = crear_torneo(client, admin["headers"], nombre="Copa de orden")

    no_admin = client.post(
        f"/torneos/{torneo['id']}/iniciar", headers=jugador["headers"]
    )
    assert no_admin.status_code == 403

    _inscribir_jugadores(client, torneo["id"], jugadores)
    _iniciar(client, admin, torneo["id"])

    tarde = client.post(
        f"/torneos/{torneo['id']}/inscribirse", headers=jugador["headers"]
    )
    assert tarde.status_code == 409

    reinicio_ajeno = client.post(
        f"/torneos/{torneo['id']}/reiniciar", headers=jugador["headers"]
    )
    assert reinicio_ajeno.status_code == 403

    reinicio = client.post(
        f"/torneos/{torneo['id']}/reiniciar", headers=admin["headers"]
    )
    assert reinicio.status_code == 200
    assert reinicio.json()["estado"] == "inscripciones_abiertas"
    assert reinicio.json()["tiene_partidas"] is False


def test_mi_partida_y_acceso_a_partidas(client, admin, crear_usuario, autenticar):
    jugadores = crear_jugadores(crear_usuario, autenticar, 4, prefijo="mipartida")
    torneo = crear_torneo(client, admin["headers"], nombre="Copa mi partida")
    _inscribir_jugadores(client, torneo["id"], jugadores)

    antes = client.get(
        f"/torneos/{torneo['id']}/mi-partida", headers=jugadores[0]["headers"]
    )
    assert antes.status_code == 200
    assert antes.json()["partida"] is None

    _iniciar(client, admin, torneo["id"])

    for jugador in jugadores:
        respuesta = client.get(
            f"/torneos/{torneo['id']}/mi-partida", headers=jugador["headers"]
        )
        assert respuesta.status_code == 200
        assert respuesta.json()["partida"] is not None

    ajeno = crear_usuario("sinpartida")
    ajeno_headers = autenticar("sinpartida")
    sin_partida = client.get(
        f"/torneos/{torneo['id']}/mi-partida", headers=ajeno_headers
    )
    assert sin_partida.json()["partida"] is None

    partida = partidas(client, torneo["id"])[0]
    publica = client.get(f"/partidas/{partida['id']}")
    assert publica.status_code == 200
    assert publica.json()["id"] == partida["id"]

    anidada = client.get(f"/torneos/{torneo['id']}/partidas/{partida['id']}")
    assert anidada.status_code == 200

    otro_torneo = crear_torneo(
        client, admin["headers"], nombre="Otro torneo", videojuego="Dota 2"
    )
    incorrecta = client.get(
        f"/torneos/{otro_torneo['id']}/partidas/{partida['id']}"
    )
    assert incorrecta.status_code == 404
