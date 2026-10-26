"""Pruebas de perfiles, roles, historial y estadísticas."""
from tests.ayudas import crear_torneo, inscribir


def test_perfil_publico_oculta_datos_privados(client, crear_usuario, autenticar, admin):
    usuario = crear_usuario("visible", email="visible@demo.com", juegos="Valorant")
    publico = client.get(f"/usuarios/{usuario['id']}")
    assert publico.status_code == 200
    assert publico.json()["username"] == "visible"
    assert publico.json()["juegos_favoritos"] == ["Valorant"]
    assert "email" not in publico.json()
    assert "tiene_password" not in publico.json()

    headers = autenticar(usuario["username"])
    propio = client.get(f"/usuarios/{usuario['id']}", headers=headers)
    assert propio.json()["email"] == "visible@demo.com"
    assert propio.json()["tiene_password"] is True

    visto_por_admin = client.get(
        f"/usuarios/{usuario['id']}", headers=admin["headers"]
    )
    assert visto_por_admin.json()["email"] == "visible@demo.com"


def test_listado_de_usuarios_solo_para_admin(client, jugador, admin):
    assert client.get("/usuarios", headers=jugador["headers"]).status_code == 403
    respuesta = client.get("/usuarios", headers=admin["headers"])
    assert respuesta.status_code == 200
    assert {usuario["username"] for usuario in respuesta.json()} == {"admin", "jugador"}


def test_editar_perfil_propio_y_ajeno(client, jugador, crear_usuario, autenticar):
    otro = crear_usuario("ajeno")
    cambios = {
        "username": "jugador_editado",
        "email": "editado@demo.com",
        "juegos_favoritos": "Valorant, Tekken 8",
    }
    propio = client.put(
        f"/usuarios/{jugador['id']}", json=cambios, headers=jugador["headers"]
    )
    assert propio.status_code == 200, propio.text
    assert propio.json()["username"] == "jugador_editado"
    assert propio.json()["juegos_favoritos"] == ["Valorant", "Tekken 8"]

    ajeno = client.put(
        f"/usuarios/{otro['id']}",
        json={"juegos_favoritos": "Dota 2"},
        headers=autenticar("jugador_editado"),
    )
    assert ajeno.status_code == 403


def test_admin_puede_editar_a_otros(client, admin, crear_usuario):
    usuario = crear_usuario("modificable")
    respuesta = client.put(
        f"/usuarios/{usuario['id']}",
        json={"email": "nuevo-correo@demo.com"},
        headers=admin["headers"],
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["email"] == "nuevo-correo@demo.com"


def test_editar_rechaza_datos_invalidos(client, jugador):
    respuesta = client.put(
        f"/usuarios/{jugador['id']}",
        json={"username": "ua", "email": "correo-invalido"},
        headers=jugador["headers"],
    )
    assert respuesta.status_code == 400
    errores = respuesta.json()["errores"]
    assert "username" in errores
    assert "email" in errores


def test_solo_admin_cambia_roles(client, jugador, admin, crear_usuario):
    objetivo = crear_usuario("objetivo")

    no_admin = client.put(
        f"/usuarios/{objetivo['id']}",
        json={"rol": "admin"},
        headers=jugador["headers"],
    )
    assert no_admin.status_code in (400, 403)

    ascenso = client.put(
        f"/usuarios/{objetivo['id']}",
        json={"rol": "admin"},
        headers=admin["headers"],
    )
    assert ascenso.status_code == 200
    assert ascenso.json()["rol"] == "admin"

    descenso = client.put(
        f"/usuarios/{objetivo['id']}",
        json={"rol": "jugador"},
        headers=admin["headers"],
    )
    assert descenso.status_code == 200
    assert descenso.json()["rol"] == "jugador"

    propio_rol = client.put(
        f"/usuarios/{admin['id']}",
        json={"rol": "jugador"},
        headers=admin["headers"],
    )
    assert propio_rol.status_code == 400


def test_baja_de_usuarios(client, admin, jugador, crear_usuario):
    propio = client.delete(f"/usuarios/{admin['id']}", headers=admin["headers"])
    assert propio.status_code == 400

    eliminable = crear_usuario("eliminable")
    eliminado = client.delete(
        f"/usuarios/{eliminable['id']}", headers=admin["headers"]
    )
    assert eliminado.status_code == 200
    assert client.get(f"/usuarios/{eliminable['id']}").status_code == 404

    no_admin = client.delete(f"/usuarios/{jugador['id']}", headers=jugador["headers"])
    assert no_admin.status_code == 403


def test_historial_y_estadisticas(client, admin, jugador):
    torneo = crear_torneo(
        client,
        admin["headers"],
        nombre="Copa de historial",
        videojuego="Tekken 8",
    )
    inscribir(client, jugador["headers"], torneo["id"])

    historial = client.get(f"/usuarios/{jugador['id']}/historial")
    assert historial.status_code == 200
    datos = historial.json()
    assert datos["usuario"]["username"] == "jugador"
    assert len(datos["historial"]) == 1
    assert datos["historial"][0]["torneo"]["id"] == torneo["id"]
    assert datos["historial"][0]["nombre"] == "jugador"

    estadisticas = client.get("/estadisticas")
    assert estadisticas.status_code == 200
    assert estadisticas.json()["usuarios"] == 2
    assert estadisticas.json()["torneos"] == 1
    assert estadisticas.json()["inscripciones"] == 1
    assert estadisticas.json()["torneos_por_estado"]["inscripciones_abiertas"] == 1


def test_usuario_inexistente(client):
    assert client.get("/usuarios/999").status_code == 404
    assert client.get("/usuarios/999/historial").status_code == 404
