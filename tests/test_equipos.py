"""Pruebas de equipos, roster, invitaciones y capitanía."""
from tests.ayudas import crear_torneo


def _crear_equipo(client, headers, nombre="Night Owls", tag="OWL", descripcion="Roster de prueba"):
    respuesta = client.post(
        "/equipos",
        json={"nombre": nombre, "tag": tag, "descripcion": descripcion},
        headers=headers,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _invitar(client, headers, equipo_id, username):
    respuesta = client.post(
        f"/equipos/{equipo_id}/invitar", json={"username": username}, headers=headers
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _aceptar(client, headers, equipo_id, membresia_id):
    respuesta = client.post(
        f"/equipos/{equipo_id}/invitaciones/{membresia_id}/aceptar",
        headers=headers,
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _formar_equipo(client, capitan, miembros, nombre="Night Owls", tag="OWL"):
    equipo = _crear_equipo(client, capitan["headers"], nombre=nombre, tag=tag)
    for miembro in miembros:
        membresia = _invitar(
            client, capitan["headers"], equipo["id"], miembro["username"]
        )
        _aceptar(client, miembro["headers"], equipo["id"], membresia["id"])
    return equipo


def test_alta_de_equipo_e_invitaciones(client, crear_usuario, autenticar):
    capitan = crear_usuario("capitan")
    capitan["headers"] = autenticar("capitan")
    miembros = [crear_usuario(f"miembro{i}") for i in range(1, 5)]
    for miembro in miembros:
        miembro["headers"] = autenticar(miembro["username"])

    equipo = _crear_equipo(client, capitan["headers"])
    assert equipo["capitan"] == "capitan"
    assert equipo["miembros"] == 1
    assert equipo["mi_rol"] == "capitan"
    assert equipo["tag"] == "OWL"

    for miembro in miembros:
        membresia = _invitar(
            client, capitan["headers"], equipo["id"], miembro["username"]
        )
        assert membresia["estado"] == "invitado"

        inbox = client.get("/equipos/invitaciones", headers=miembro["headers"])
        assert inbox.status_code == 200
        assert any(item["id"] == membresia["id"] for item in inbox.json())

        _aceptar(client, miembro["headers"], equipo["id"], membresia["id"])

    detalle = client.get(f"/equipos/{equipo['id']}", headers=capitan["headers"]).json()
    assert detalle["miembros"] == 5
    assert len(detalle["roster"]) == 5
    assert detalle["mi_rol"] == "capitan"
    assert all(item["estado"] == "activo" for item in detalle["roster"])

    mios = client.get("/equipos/mios", headers=miembros[0]["headers"]).json()
    assert [item["id"] for item in mios] == [equipo["id"]]

    vacio = client.get("/equipos/invitaciones", headers=miembros[0]["headers"])
    assert vacio.json() == []

    repetida = client.post(
        f"/equipos/{equipo['id']}/invitar",
        json={"username": miembros[0]["username"]},
        headers=capitan["headers"],
    )
    assert repetida.status_code == 409

    a_si_mismo = client.post(
        f"/equipos/{equipo['id']}/invitar",
        json={"username": "capitan"},
        headers=capitan["headers"],
    )
    assert a_si_mismo.status_code == 409

    inexistente = client.post(
        f"/equipos/{equipo['id']}/invitar",
        json={"username": "nadie"},
        headers=capitan["headers"],
    )
    assert inexistente.status_code == 404

    sin_permiso = client.post(
        f"/equipos/{equipo['id']}/invitar",
        json={"username": "nadie"},
        headers=miembros[0]["headers"],
    )
    assert sin_permiso.status_code == 403


def test_editar_y_eliminar_equipo(client, crear_usuario, autenticar, admin):
    capitan = crear_usuario("lider")
    capitan["headers"] = autenticar("lider")
    miembro = crear_usuario("integrante")
    miembro["headers"] = autenticar("integrante")

    equipo = _formar_equipo(client, capitan, [miembro])
    editado = client.put(
        f"/equipos/{equipo['id']}",
        json={"nombre": "Night Owls Pro", "tag": "OWLP", "descripcion": "Nueva"},
        headers=capitan["headers"],
    )
    assert editado.status_code == 200, editado.text
    assert editado.json()["nombre"] == "Night Owls Pro"
    assert editado.json()["tag"] == "OWLP"

    ajeno = client.put(
        f"/equipos/{equipo['id']}",
        json={"nombre": "Otro nombre"},
        headers=miembro["headers"],
    )
    assert ajeno.status_code == 403

    borrado_ajeno = client.delete(
        f"/equipos/{equipo['id']}", headers=miembro["headers"]
    )
    assert borrado_ajeno.status_code == 403

    borrado = client.delete(f"/equipos/{equipo['id']}", headers=admin["headers"])
    assert borrado.status_code == 204
    assert borrado.content == b""
    assert client.get(f"/equipos/{equipo['id']}").status_code == 404


def test_validaciones_de_equipo(client, crear_usuario, autenticar):
    capitan = crear_usuario("creador")
    capitan["headers"] = autenticar("creador")
    _crear_equipo(client, capitan["headers"], nombre="Equipo Único")

    vacio = client.post(
        "/equipos", json={"nombre": ""}, headers=capitan["headers"]
    )
    assert vacio.status_code == 400
    assert "nombre" in vacio.json()["errores"]

    duplicado = client.post(
        "/equipos",
        json={"nombre": "equipo único"},
        headers=capitan["headers"],
    )
    assert duplicado.status_code == 400
    assert "nombre" in duplicado.json()["errores"]

    tag_largo = client.post(
        "/equipos",
        json={"nombre": "Otro equipo", "tag": "ETIQUETAMUYLARGA"},
        headers=capitan["headers"],
    )
    assert tag_largo.status_code == 400
    assert "tag" in tag_largo.json()["errores"]


def test_rechazo_salida_y_expulsion(client, crear_usuario, autenticar):
    capitan = crear_usuario("capitan_baja")
    capitan["headers"] = autenticar("capitan_baja")
    miembro = crear_usuario("miembro_baja")
    miembro["headers"] = autenticar("miembro_baja")

    equipo = _crear_equipo(client, capitan["headers"])
    membresia = _invitar(client, capitan["headers"], equipo["id"], "miembro_baja")

    rechazo = client.post(
        f"/equipos/{equipo['id']}/invitaciones/{membresia['id']}/rechazar",
        headers=miembro["headers"],
    )
    assert rechazo.status_code == 200
    assert client.get(f"/equipos/{equipo['id']}").json()["miembros"] == 1

    otra_vez = client.post(
        f"/equipos/{equipo['id']}/invitaciones/{membresia['id']}/aceptar",
        headers=miembro["headers"],
    )
    assert otra_vez.status_code == 409

    membresia = _invitar(client, capitan["headers"], equipo["id"], "miembro_baja")
    _aceptar(client, miembro["headers"], equipo["id"], membresia["id"])

    salida_capitan = client.post(
        f"/equipos/{equipo['id']}/salir", headers=capitan["headers"]
    )
    assert salida_capitan.status_code == 409

    salida = client.post(
        f"/equipos/{equipo['id']}/salir", headers=miembro["headers"]
    )
    assert salida.status_code == 200
    assert client.get(f"/equipos/{equipo['id']}").json()["miembros"] == 1

    membresia = _invitar(client, capitan["headers"], equipo["id"], "miembro_baja")
    _aceptar(client, miembro["headers"], equipo["id"], membresia["id"])

    expulsion_ajena = client.delete(
        f"/equipos/{equipo['id']}/miembros/{membresia['id']}",
        headers=miembro["headers"],
    )
    assert expulsion_ajena.status_code == 403

    expulsion = client.delete(
        f"/equipos/{equipo['id']}/miembros/{membresia['id']}",
        headers=capitan["headers"],
    )
    assert expulsion.status_code == 204
    assert expulsion.content == b""
    assert client.get(f"/equipos/{equipo['id']}").json()["miembros"] == 1


def test_transferencia_de_capitania(client, crear_usuario, autenticar):
    capitan = crear_usuario("viejo_capitan")
    capitan["headers"] = autenticar("viejo_capitan")
    nuevo = crear_usuario("nuevo_capitan")
    nuevo["headers"] = autenticar("nuevo_capitan")

    equipo = _formar_equipo(client, capitan, [nuevo])

    ajeno = client.post(
        f"/equipos/{equipo['id']}/capitan/{nuevo['id']}",
        headers=nuevo["headers"],
    )
    assert ajeno.status_code == 403

    transferencia = client.post(
        f"/equipos/{equipo['id']}/capitan/{nuevo['id']}",
        headers=capitan["headers"],
    )
    assert transferencia.status_code == 200

    detalle = client.get(f"/equipos/{equipo['id']}", headers=nuevo["headers"]).json()
    assert detalle["capitan_id"] == nuevo["id"]
    assert detalle["capitan"] == "nuevo_capitan"
    assert detalle["mi_rol"] == "capitan"

    edicion = client.put(
        f"/equipos/{equipo['id']}",
        json={"descripcion": "Ahora manda el nuevo capitán"},
        headers=nuevo["headers"],
    )
    assert edicion.status_code == 200


def test_equipo_en_torneo_y_bloqueo_de_roster(client, admin, crear_usuario, autenticar):
    a1 = crear_usuario("alfa1")
    a1["headers"] = autenticar("alfa1")
    alfas = [crear_usuario(f"alfa{i}") for i in range(2, 6)]
    for jugador in alfas:
        jugador["headers"] = autenticar(jugador["username"])
    b1 = crear_usuario("beta1")
    b1["headers"] = autenticar("beta1")
    betas = [crear_usuario(f"beta{i}") for i in range(2, 5)]
    for jugador in betas:
        jugador["headers"] = autenticar(jugador["username"])

    equipo_a = _formar_equipo(
        client, a1, alfas[:3], nombre="Alfa Team", tag="ALF"
    )
    torneo = crear_torneo(
        client,
        admin["headers"],
        nombre="Copa por equipos",
        modalidad="equipos",
        jugadores_por_equipo=5,
        formato="BO1",
    )

    disponibles = client.get(
        f"/equipos/{equipo_a['id']}/torneos-disponibles", headers=a1["headers"]
    )
    assert disponibles.status_code == 200
    assert [item["id"] for item in disponibles.json()] == [torneo["id"]]

    incompleto = client.post(
        f"/torneos/{torneo['id']}/inscribirse",
        json={"equipo_id": equipo_a["id"]},
        headers=a1["headers"],
    )
    assert incompleto.status_code == 409
    assert "5 integrantes" in incompleto.json()["detail"]

    membresia = _invitar(client, a1["headers"], equipo_a["id"], alfas[3]["username"])
    _aceptar(client, alfas[3]["headers"], equipo_a["id"], membresia["id"])

    antes = client.get(
        f"/torneos/{torneo['id']}/equipos-disponibles", headers=a1["headers"]
    ).json()
    assert [item["id"] for item in antes] == [equipo_a["id"]]

    inscripcion = client.post(
        f"/torneos/{torneo['id']}/inscribirse",
        json={"equipo_id": equipo_a["id"]},
        headers=a1["headers"],
    )
    assert inscripcion.status_code == 201, inscripcion.text
    assert inscripcion.json()["equipo_id"] == equipo_a["id"]
    assert len(inscripcion.json()["roster"]) == 5

    despues = client.get(
        f"/torneos/{torneo['id']}/equipos-disponibles", headers=a1["headers"]
    ).json()
    assert despues == []

    disponibles = client.get(
        f"/equipos/{equipo_a['id']}/torneos-disponibles", headers=a1["headers"]
    ).json()
    assert disponibles == []

    repetida = client.post(
        f"/torneos/{torneo['id']}/inscribirse",
        json={"equipo_id": equipo_a["id"]},
        headers=a1["headers"],
    )
    assert repetida.status_code == 409

    equipo_b = _formar_equipo(
        client, b1, [alfas[0], *betas], nombre="Beta Team", tag="BET"
    )
    cruce = client.post(
        f"/torneos/{torneo['id']}/inscribirse",
        json={"equipo_id": equipo_b["id"]},
        headers=b1["headers"],
    )
    assert cruce.status_code == 409
    assert "ya están inscriptos" in cruce.json()["detail"]

    invitacion_bloqueada = client.post(
        f"/equipos/{equipo_a['id']}/invitar",
        json={"username": "beta2"},
        headers=a1["headers"],
    )
    assert invitacion_bloqueada.status_code == 409

    salida_bloqueada = client.post(
        f"/equipos/{equipo_a['id']}/salir", headers=alfas[0]["headers"]
    )
    assert salida_bloqueada.status_code == 409

    detalle = client.get(f"/equipos/{equipo_a['id']}", headers=a1["headers"]).json()
    membresia_alfa = next(
        item for item in detalle["roster"] if item["usuario_id"] == alfas[0]["id"]
    )
    expulsion_bloqueada = client.delete(
        f"/equipos/{equipo_a['id']}/miembros/{membresia_alfa['id']}",
        headers=a1["headers"],
    )
    assert expulsion_bloqueada.status_code == 409

    borrado_bloqueado = client.delete(
        f"/equipos/{equipo_a['id']}", headers=a1["headers"]
    )
    assert borrado_bloqueado.status_code == 409

    cancelada = client.delete(
        f"/torneos/{torneo['id']}/inscribirse", headers=a1["headers"]
    )
    assert cancelada.status_code == 204

    invitacion_libre = client.post(
        f"/equipos/{equipo_a['id']}/invitar",
        json={"username": "beta3"},
        headers=a1["headers"],
    )
    assert invitacion_libre.status_code == 201

    borrado = client.delete(f"/equipos/{equipo_a['id']}", headers=a1["headers"])
    assert borrado.status_code == 204


def test_equipo_inexistente(client):
    assert client.get("/equipos/999").status_code == 404
    assert client.post("/equipos/999/invitar", json={"username": "x"}).status_code == 401
