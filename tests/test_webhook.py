"""Pruebas del webhook firmado de CS2."""
import hashlib
import hmac
import json
import unittest

from models import db
from tests.base import BaseTestCase


class WebhookTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin, self.jugadores, self.torneo = self.iniciar_con(2)
        self.partida = self.torneo.partidas[0]
        self.secreto = "secreto-de-pruebas"

    def activar(self, secreto=True):
        self.app.config["MODO_SERVIDORES"] = True
        self.app.config["CS2_WEBHOOK_SECRET"] = self.secreto if secreto else ""

    def enviar(self, cuerpo, firma=None):
        if firma is None:
            firma = hmac.new(self.secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
        return self.client.post(
            "/api/cs2/webhook/match-result",
            data=cuerpo,
            content_type="application/json",
            headers={"X-CS2-Signature": firma},
        )

    def cuerpo(self, **datos):
        return json.dumps(
            {"partida_id": self.partida.id, "puntaje1": 1, "puntaje2": 0, **datos}
        ).encode()

    def test_desactivado_responde_404(self):
        respuesta = self.enviar(self.cuerpo())

        self.assertEqual(respuesta.status_code, 404)

    def test_sin_secreto_responde_503(self):
        self.activar(secreto=False)

        respuesta = self.enviar(self.cuerpo())

        self.assertEqual(respuesta.status_code, 503)
        self.assertIn("no está configurado", respuesta.get_json()["error"])

    def test_firma_invalida_responde_401(self):
        self.activar()

        respuesta = self.enviar(self.cuerpo(), firma="firma-falsa")

        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.get_json(), {"error": "Firma inválida."})
        db.session.refresh(self.partida)
        self.assertEqual(self.partida.estado, "pendiente")

    def test_firma_valida_cierra_la_partida(self):
        self.activar()

        respuesta = self.enviar(self.cuerpo(puntaje1=1, puntaje2=0))

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.get_json()
        self.assertEqual(datos["partida_id"], self.partida.id)
        self.assertEqual(datos["torneo_estado"], "finalizado")
        self.assertEqual(datos["ganador"], self.partida.participante1.usuario.username)

        db.session.expire_all()
        self.assertEqual(self.partida.estado, "finalizada")
        self.assertEqual(self.partida.resultado.estado, "confirmado")
        self.assertIsNone(self.partida.resultado.registrado_por_id)
        self.assertEqual(self.torneo.campeon.usuario, self.partida.participante1.usuario)

    def test_datos_incompletos_responde_400(self):
        self.activar()

        respuesta = self.enviar(json.dumps({"partida_id": self.partida.id}).encode())

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("puntaje1", respuesta.get_json()["error"])

    def test_partida_inexistente_responde_404(self):
        self.activar()

        respuesta = self.enviar(
            json.dumps({"partida_id": 999999, "puntaje1": 1, "puntaje2": 0}).encode()
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_marcador_invalido_responde_400(self):
        self.activar()

        respuesta = self.enviar(self.cuerpo(puntaje1=1, puntaje2=1))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("detalles", respuesta.get_json())

    def test_no_se_procesa_dos_veces(self):
        self.activar()
        self.enviar(self.cuerpo())

        respuesta = self.enviar(self.cuerpo(puntaje1=0, puntaje2=1))

        self.assertEqual(respuesta.status_code, 409)


if __name__ == "__main__":
    unittest.main()
