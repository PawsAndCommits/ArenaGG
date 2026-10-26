"""Fixtures compartidas por las pruebas de la API."""
import pytest
from fastapi.testclient import TestClient

from app_factory import create_app
from config import Settings
from services import usuarios as usuarios_sv


@pytest.fixture()
def app(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'arenagg-pruebas.db').as_posix()}",
        secret_key="clave-de-pruebas-arenagg-2026-segura",
        token_expiracion_minutos=60,
        cors_origins="http://localhost:5173,http://127.0.0.1:5173",
    )
    aplicacion = create_app(settings)
    yield aplicacion
    aplicacion.state.engine.dispose()


@pytest.fixture()
def client(app):
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture()
def crear_usuario(app):
    def _crear(
        username: str,
        rol: str = "jugador",
        password: str = "Jugador1234",
        email: str | None = None,
        juegos: str = "",
    ) -> dict:
        with app.state.session_factory() as db:
            usuario = usuarios_sv.registrar_usuario(
                db,
                {
                    "username": username,
                    "email": email or f"{username.lower()}@pruebas.com",
                    "password": password,
                    "juegos_favoritos": juegos,
                },
                rol=rol,
            )
            return {
                "id": usuario.id,
                "username": usuario.username,
                "password": password,
            }

    return _crear


@pytest.fixture()
def autenticar(client):
    def _autenticar(username: str, password: str = "Jugador1234") -> dict:
        respuesta = client.post(
            "/auth/login",
            data={"username": username, "password": password},
        )
        assert respuesta.status_code == 200, respuesta.text
        return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}

    return _autenticar


@pytest.fixture()
def admin(crear_usuario, autenticar):
    usuario = crear_usuario("admin", rol="admin", password="Admin1234")
    usuario["headers"] = autenticar("admin", "Admin1234")
    return usuario


@pytest.fixture()
def jugador(crear_usuario, autenticar):
    usuario = crear_usuario("jugador", password="Jugador1234")
    usuario["headers"] = autenticar("jugador", "Jugador1234")
    return usuario
