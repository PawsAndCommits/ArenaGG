"""Pruebas de registro, login y sesión JWT."""
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from tests.ayudas import auth


def test_registro_crea_cuenta_y_devuelve_token(client):
    respuesta = client.post(
        "/auth/registro",
        json={
            "username": "nueva_cuenta",
            "email": "nueva@demo.com",
            "password": "Clave1234",
            "password_confirmacion": "Clave1234",
            "juegos_favoritos": "Valorant, Rocket League",
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    assert datos["token_type"] == "bearer"
    assert datos["expires_in"] > 0
    assert datos["usuario"]["username"] == "nueva_cuenta"
    assert datos["usuario"]["email"] == "nueva@demo.com"
    assert datos["usuario"]["rol"] == "jugador"
    assert datos["usuario"]["tiene_password"] is True
    assert datos["usuario"]["juegos_favoritos"] == ["Valorant", "Rocket League"]
    assert "password_hash" not in datos["usuario"]

    perfil = client.get("/usuarios/me", headers=auth(datos["access_token"]))
    assert perfil.status_code == 200
    assert perfil.json()["id"] == datos["usuario"]["id"]


def test_registro_rechaza_usuario_y_correo_repetidos(client):
    base = {
        "username": "repetido",
        "email": "repetido@demo.com",
        "password": "Clave1234",
    }
    assert client.post("/auth/registro", json=base).status_code == 201

    mismo_usuario = client.post(
        "/auth/registro",
        json={**base, "username": "REPETIDO", "email": "otro@demo.com"},
    )
    assert mismo_usuario.status_code == 400
    assert "username" in mismo_usuario.json()["errores"]

    mismo_correo = client.post(
        "/auth/registro",
        json={**base, "username": "otro_usuario", "email": "REPETIDO@demo.com"},
    )
    assert mismo_correo.status_code == 400
    assert "email" in mismo_correo.json()["errores"]


@pytest.mark.parametrize(
    ("datos", "campo"),
    [
        ({"username": "ab", "email": "ab@demo.com", "password": "Clave1234"}, "username"),
        ({"username": "buen_user", "email": "sin-arroba", "password": "Clave1234"}, "email"),
        ({"username": "buen_user", "email": "bueno@demo.com", "password": "corta"}, "password"),
        (
            {
                "username": "buen_user",
                "email": "bueno@demo.com",
                "password": "Clave1234",
                "password_confirmacion": "OtraClave1234",
            },
            "password_confirmacion",
        ),
    ],
)
def test_registro_valida_datos(client, datos, campo):
    respuesta = client.post("/auth/registro", json=datos)
    assert respuesta.status_code == 400
    assert campo in respuesta.json()["errores"]


def test_login_con_usuario_o_correo(client, jugador):
    por_usuario = client.post(
        "/auth/login",
        data={"username": "jugador", "password": "Jugador1234"},
    )
    assert por_usuario.status_code == 200
    assert por_usuario.json()["usuario"]["username"] == "jugador"

    por_correo = client.post(
        "/auth/login",
        data={"username": "jugador@pruebas.com", "password": "Jugador1234"},
    )
    assert por_correo.status_code == 200
    assert por_correo.json()["usuario"]["id"] == jugador["id"]

    incorrecta = client.post(
        "/auth/login",
        data={"username": "jugador", "password": "NoEsLaClave1"},
    )
    assert incorrecta.status_code == 401
    assert "incorrectos" in incorrecta.json()["detail"]


def test_login_de_usuario_inexistente(client):
    respuesta = client.post(
        "/auth/login",
        data={"username": "fantasma", "password": "Jugador1234"},
    )
    assert respuesta.status_code == 401


def test_endpoints_protegidos_exigen_bearer(client, app):
    sin_token = client.get("/usuarios/me")
    assert sin_token.status_code == 401
    assert sin_token.headers["www-authenticate"] == "Bearer"

    token_invalido = client.get(
        "/usuarios/me", headers={"Authorization": "Bearer no-es-un-jwt"}
    )
    assert token_invalido.status_code == 401

    expirado = jwt.encode(
        {
            "sub": "1",
            "hv": "huella",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        app.state.settings.secret_key,
        algorithm="HS256",
    )
    respuesta = client.get("/usuarios/me", headers=auth(expirado))
    assert respuesta.status_code == 401
    assert "expiró" in respuesta.json()["detail"]


def test_auth_me_devuelve_el_mismo_perfil(client, jugador):
    desde_auth = client.get("/auth/me", headers=jugador["headers"])
    desde_usuarios = client.get("/usuarios/me", headers=jugador["headers"])
    assert desde_auth.status_code == 200
    assert desde_auth.json() == desde_usuarios.json()


def test_cambio_de_password_invalida_el_token_anterior(client, jugador):
    respuesta = client.put(
        f"/usuarios/{jugador['id']}",
        json={
            "password": "NuevaClave1234",
            "password_actual": "Jugador1234",
            "password_confirmacion": "NuevaClave1234",
        },
        headers=jugador["headers"],
    )
    assert respuesta.status_code == 200, respuesta.text

    token_viejo = client.get("/usuarios/me", headers=jugador["headers"])
    assert token_viejo.status_code == 401

    login_viejo = client.post(
        "/auth/login",
        data={"username": "jugador", "password": "Jugador1234"},
    )
    assert login_viejo.status_code == 401

    login_nuevo = client.post(
        "/auth/login",
        data={"username": "jugador", "password": "NuevaClave1234"},
    )
    assert login_nuevo.status_code == 200
    nuevo_token = auth(login_nuevo.json()["access_token"])
    assert client.get("/usuarios/me", headers=nuevo_token).status_code == 200


def test_cambio_de_password_exige_la_actual(client, jugador):
    respuesta = client.put(
        f"/usuarios/{jugador['id']}",
        json={"password": "NuevaClave1234", "password_actual": "Incorrecta1234"},
        headers=jugador["headers"],
    )
    assert respuesta.status_code == 400
    assert "password_actual" in respuesta.json()["errores"]
