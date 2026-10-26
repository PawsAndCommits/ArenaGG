"""Pruebas de cuentas creadas con Steam, sin contraseña local."""
import unittest

import services as sv
from models import Usuario, db
from tests.base import BaseTestCase


class CuentasTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.usuario = Usuario(
            username="steam_user",
            email=None,
            rol="jugador",
            password_hash=None,
            steam_id="76561198000000000",
            steam_persona_name="Steam User",
            steam_profile_url="https://steamcommunity.com/profiles/76561198000000000",
        )
        db.session.add(self.usuario)
        db.session.commit()

    def test_cuenta_sin_password_no_puede_entrar_con_password(self):
        respuesta = self.client.post(
            "/login", data={"identificador": "steam_user", "password": "loquesea"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Usuario o contraseña incorrectos.", respuesta.get_data(as_text=True))

    def test_autenticar_no_falla_si_no_hay_password(self):
        with self.assertRaises(sv.ErrorNegocio) as contexto:
            sv.autenticar("steam_user", "")

        self.assertEqual(contexto.exception.codigo, 401)

    def test_puede_definir_una_password_local(self):
        sv.actualizar_usuario(
            self.usuario,
            {"password": "NuevaClave123", "password_confirmacion": "NuevaClave123"},
            self.usuario,
        )

        self.assertTrue(self.usuario.tiene_password)
        self.assertTrue(self.usuario.check_password("NuevaClave123"))
        respuesta = self.iniciar_sesion(self.usuario, "NuevaClave123")
        self.assertEqual(respuesta.status_code, 302)

    def test_cambio_posterior_exige_la_password_actual(self):
        sv.actualizar_usuario(
            self.usuario,
            {"password": "NuevaClave123", "password_confirmacion": "NuevaClave123"},
            self.usuario,
        )

        with self.assertRaises(sv.ErrorValidacion) as contexto:
            sv.actualizar_usuario(
                self.usuario,
                {"password": "OtraClave123", "password_confirmacion": "OtraClave123"},
                self.usuario,
            )
        self.assertIn("password_actual", contexto.exception.errores)

        sv.actualizar_usuario(
            self.usuario,
            {
                "password": "OtraClave123",
                "password_confirmacion": "OtraClave123",
                "password_actual": "NuevaClave123",
            },
            self.usuario,
        )
        self.assertTrue(self.usuario.check_password("OtraClave123"))

    def test_perfil_de_cuenta_steam(self):
        sv.actualizar_usuario(
            self.usuario,
            {"password": "NuevaClave123", "password_confirmacion": "NuevaClave123"},
            self.usuario,
        )
        self.iniciar_sesion(self.usuario, "NuevaClave123")

        respuesta = self.client.get("/perfil")

        self.assertEqual(respuesta.status_code, 200)
        texto = respuesta.get_data(as_text=True)
        self.assertIn("steam_user", texto)
        self.assertIn("Steam vinculado", texto)

    def test_perfil_publico_sin_email(self):
        respuesta = self.client.get(f"/jugadores/{self.usuario.id}")

        self.assertEqual(respuesta.status_code, 200)
        texto = respuesta.get_data(as_text=True)
        self.assertIn("steam_user", texto)
        self.assertNotIn("Correo electrónico", texto)

    def test_eliminar_cuenta_con_historial(self):
        admin = self.crear_usuario("admin_cuentas", rol="admin")
        jugador = self.crear_usuario("con_historial")
        torneo = self.crear_torneo(admin, nombre="Copa historial", cupo=2)
        self.inscribir(torneo, jugador)
        self.inscribir(torneo, self.crear_usuario("rival_historial"))
        sv.iniciar_torneo(torneo)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            sv.eliminar_usuario(jugador, admin)
        self.assertEqual(contexto.exception.codigo, 409)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            sv.eliminar_usuario(admin, admin)
        self.assertEqual(contexto.exception.codigo, 400)


if __name__ == "__main__":
    unittest.main()
