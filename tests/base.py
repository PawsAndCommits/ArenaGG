"""Utilidades comunes para las pruebas."""
import os
import tempfile
import unittest
from datetime import timedelta

_CARPETA_IMPORT = tempfile.mkdtemp(prefix="arenagg-import-")
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault(
    "DATABASE_URL", "sqlite:///" + os.path.join(_CARPETA_IMPORT, "import.db")
)

import services as sv
from app import create_app
from models import ahora, db


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory(prefix="arenagg-test-")
        ruta = os.path.join(self.carpeta.name, "pruebas.db")
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "clave-de-pruebas",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///" + ruta,
                "CSRF_ENABLED": False,
                "MODO_SERVIDORES": False,
                "STEAM_API_KEY": "",
                "CS2_WEBHOOK_SECRET": "",
            }
        )
        self.contexto = self.app.app_context()
        self.contexto.push()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.contexto.pop()
        self.carpeta.cleanup()

    def crear_usuario(self, username, rol="jugador", password="Jugador1234"):
        return sv.registrar_usuario(
            {
                "username": username,
                "email": f"{username.lower()}@pruebas.com",
                "password": password,
            },
            rol=rol,
        )

    def crear_torneo(
        self,
        admin,
        nombre="Copa de prueba",
        modalidad="individual",
        formato="BO1",
        cupo=8,
        jugadores_por_equipo=None,
        estado="inscripciones_abiertas",
    ):
        datos = {
            "nombre": nombre,
            "videojuego": "Valorant",
            "fecha": (ahora() + timedelta(days=2)).isoformat(),
            "cupo_maximo": cupo,
            "estado": estado,
            "modalidad": modalidad,
            "formato": formato,
        }
        if jugadores_por_equipo:
            datos["jugadores_por_equipo"] = jugadores_por_equipo
        return sv.crear_torneo(datos, admin)

    def inscribir(self, torneo, usuario, **datos):
        return sv.inscribir(torneo, usuario, datos)

    def iniciar_con(self, cantidad, formato="BO1"):
        admin = self.crear_usuario(f"admin{cantidad}", rol="admin")
        jugadores = [
            self.crear_usuario(f"jugador{cantidad}_{indice}")
            for indice in range(1, cantidad + 1)
        ]
        torneo = self.crear_torneo(
            admin,
            nombre=f"Copa de {cantidad}",
            formato=formato,
            cupo=max(cantidad, 2),
        )
        for jugador in jugadores:
            self.inscribir(torneo, jugador)
        sv.iniciar_torneo(torneo)
        return admin, jugadores, torneo

    def iniciar_sesion(self, usuario, password="Jugador1234"):
        respuesta = self.client.post(
            "/login",
            data={"identificador": usuario.username, "password": password},
            follow_redirects=False,
        )
        self.assertEqual(respuesta.status_code, 302)
        return respuesta
