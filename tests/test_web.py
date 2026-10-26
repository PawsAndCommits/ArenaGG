"""Pruebas de renderizado web y del flujo HTTP principal."""
import unittest
from datetime import timedelta

import services as sv
from models import Torneo, Usuario, ahora, db
from tests.base import BaseTestCase


class WebTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.crear_usuario("web_admin", rol="admin")
        self.jugador = self.crear_usuario("web_player")
        self.torneo = self.crear_torneo(
            self.admin, nombre="Copa Web", cupo=4
        )

    def test_paginas_publicas(self):
        self.inscribir(self.torneo, self.jugador)

        paginas = [
            "/",
            "/torneos",
            f"/torneos/{self.torneo.id}",
            f"/jugadores/{self.jugador.id}",
            "/equipos/",
        ]
        for ruta in paginas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200)

        respuesta = self.client.get("/")
        self.assertIn("ArenaGG", respuesta.get_data(as_text=True))

    def test_pagina_inexistente(self):
        respuesta = self.client.get("/no-existe")

        self.assertEqual(respuesta.status_code, 404)
        self.assertIn("404", respuesta.get_data(as_text=True))

    def test_detalle_muestra_el_torneo_y_los_inscriptos(self):
        self.inscribir(self.torneo, self.jugador)

        respuesta = self.client.get(f"/torneos/{self.torneo.id}")

        texto = respuesta.get_data(as_text=True)
        self.assertIn("Copa Web", texto)
        self.assertIn(self.jugador.username, texto)

    def test_detalle_y_sala_de_una_partida(self):
        admin, jugadores, torneo = self.iniciar_con(4)
        jugador = jugadores[0]
        partida = next(p for p in torneo.partidas if p.incluye_usuario(jugador))
        self.iniciar_sesion(jugador)

        detalle = self.client.get(f"/torneos/{torneo.id}")
        self.assertEqual(detalle.status_code, 200)
        self.assertIn("Copa de 4", detalle.get_data(as_text=True))

        sala = self.client.get(f"/torneos/{torneo.id}/partidas/{partida.id}")
        self.assertEqual(sala.status_code, 200)
        texto = sala.get_data(as_text=True)
        self.assertIn(jugador.username, texto)
        self.assertIn("Cargar resultado", texto)

    def test_admin_crea_un_torneo_por_formulario(self):
        self.iniciar_sesion(self.admin, "Jugador1234")

        formulario = self.client.get("/torneos/nuevo")
        self.assertEqual(formulario.status_code, 200)

        respuesta = self.client.post(
            "/torneos/nuevo",
            data={
                "nombre": "Nuevo desde la web",
                "descripcion": "Torneo creado por formulario",
                "videojuego": "Valorant",
                "fecha": (ahora() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
                "cupo_maximo": "8",
                "modalidad": "individual",
                "formato": "BO3",
                "estado": "inscripciones_abiertas",
                "premio": "Trofeo",
                "reglas": "Fair play",
            },
            follow_redirects=True,
        )

        self.assertEqual(respuesta.status_code, 200)
        creado = Torneo.query.filter_by(nombre="Nuevo desde la web").first()
        self.assertIsNotNone(creado)
        self.assertEqual(creado.formato, "BO3")
        self.assertEqual(creado.creado_por_id, self.admin.id)

    def test_un_jugador_no_entra_al_formulario_de_admin(self):
        self.iniciar_sesion(self.jugador)

        respuesta = self.client.get("/torneos/nuevo")

        self.assertEqual(respuesta.status_code, 403)

    def test_inscripcion_por_formulario(self):
        self.iniciar_sesion(self.jugador)

        respuesta = self.client.post(
            f"/torneos/{self.torneo.id}/inscribirse", data={}, follow_redirects=True
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNotNone(self.torneo.inscripcion_de(self.jugador))
        self.assertIn("Quedaste inscripto", respuesta.get_data(as_text=True))

    def test_resultado_confirmado_por_http(self):
        admin, jugadores, torneo = self.iniciar_con(2, formato="BO1")
        p1, p2 = jugadores
        partida = torneo.partidas[0]

        self.iniciar_sesion(p1)
        carga = self.client.post(
            f"/torneos/{torneo.id}/partidas/{partida.id}/resultado",
            data={"puntaje1": "1", "puntaje2": "0"},
            follow_redirects=True,
        )
        self.assertEqual(carga.status_code, 200)
        self.assertIn("confirmarlo el rival", carga.get_data(as_text=True))

        self.client.post("/logout")
        self.iniciar_sesion(p2)
        confirmacion = self.client.post(
            f"/torneos/{torneo.id}/partidas/{partida.id}/confirmar",
            follow_redirects=True,
        )
        self.assertEqual(confirmacion.status_code, 200)

        db.session.expire_all()
        self.assertEqual(partida.estado, "finalizada")
        self.assertEqual(torneo.estado, "finalizado")
        self.assertEqual(torneo.campeon.id, partida.participante1_id)


class ApiTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.crear_usuario("api_admin", rol="admin")
        self.jugador = self.crear_usuario("api_player")

    def token(self, usuario, password="Jugador1234"):
        respuesta = self.client.post(
            "/api/auth/login",
            json={"username": usuario.username, "password": password},
        )
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.get_json()["token"]

    def test_login_y_me(self):
        token = self.token(self.jugador)

        respuesta = self.client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json()["username"], "api_player")
        self.assertNotIn("password_hash", respuesta.get_json())

    def test_sin_token_responde_401(self):
        respuesta = self.client.get("/api/auth/me")

        self.assertEqual(respuesta.status_code, 401)

    def test_jugador_no_crea_torneos(self):
        token = self.token(self.jugador)

        respuesta = self.client.post(
            "/api/torneos",
            json={
                "nombre": "No permitido",
                "videojuego": "Valorant",
                "fecha": (ahora() + timedelta(days=1)).isoformat(),
                "cupo_maximo": 4,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_admin_crea_y_consulta_un_torneo(self):
        token = self.token(self.admin)

        creacion = self.client.post(
            "/api/torneos",
            json={
                "nombre": "Copa API",
                "videojuego": "Valorant",
                "fecha": (ahora() + timedelta(days=2)).isoformat(),
                "cupo_maximo": 8,
                "formato": "BO3",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(creacion.status_code, 201)
        datos = creacion.get_json()["torneo"]
        self.assertEqual(datos["nombre"], "Copa API")
        self.assertEqual(datos["formato"], "BO3")

        consulta = self.client.get(f"/api/torneos/{datos['id']}")
        self.assertEqual(consulta.status_code, 200)
        self.assertEqual(consulta.get_json()["modalidad"], "individual")

    def test_torneo_inexistente_responde_404_json(self):
        respuesta = self.client.get("/api/torneos/999999")

        self.assertEqual(respuesta.status_code, 404)
        self.assertIn("error", respuesta.get_json())


if __name__ == "__main__":
    unittest.main()
