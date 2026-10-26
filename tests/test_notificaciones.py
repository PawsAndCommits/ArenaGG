"""Pruebas de la bandeja de notificaciones."""
import unittest

from models import Notificacion, db
from tests.base import BaseTestCase


class NotificacionesTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.usuario = self.crear_usuario("notificado")
        self.otro = self.crear_usuario("ajeno")

    def crear(self, usuario, titulo, url=None, leida=False, tipo="partida"):
        notificacion = Notificacion(
            usuario_id=usuario.id,
            tipo=tipo,
            titulo=titulo,
            mensaje=f"Mensaje de {titulo}",
            url=url,
            leida=leida,
        )
        db.session.add(notificacion)
        db.session.commit()
        return notificacion

    def test_requiere_sesion(self):
        respuesta = self.client.get("/notificaciones/")

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login", respuesta.headers["Location"])

    def test_bandeja_solo_muestra_las_propias(self):
        propia = self.crear(self.usuario, "Tu partida está lista")
        ajena = self.crear(self.otro, "Partida de otra persona")
        self.iniciar_sesion(self.usuario)

        respuesta = self.client.get("/notificaciones/")

        self.assertEqual(respuesta.status_code, 200)
        texto = respuesta.get_data(as_text=True)
        self.assertIn(propia.titulo, texto)
        self.assertNotIn(ajena.titulo, texto)

    def test_filtro_sin_leer(self):
        pendiente = self.crear(self.usuario, "Pendiente de leer")
        self.crear(self.usuario, "Ya leída", leida=True)
        self.iniciar_sesion(self.usuario)

        respuesta = self.client.get("/notificaciones/?filtro=sin_leer")

        self.assertEqual(respuesta.status_code, 200)
        texto = respuesta.get_data(as_text=True)
        self.assertIn(pendiente.titulo, texto)
        self.assertEqual(texto.count("notif-fila"), 1)

    def test_marcar_leida_por_json(self):
        notificacion = self.crear(self.usuario, "Para marcar")
        self.iniciar_sesion(self.usuario)

        respuesta = self.client.post(
            f"/notificaciones/{notificacion.id}/leer",
            headers={"Accept": "application/json"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json(), {"ok": True, "sin_leer": 0})
        db.session.refresh(notificacion)
        self.assertTrue(notificacion.leida)

    def test_abrir_redirige_a_una_url_interna(self):
        notificacion = self.crear(self.usuario, "Ir al torneo", url="/torneos/7")
        self.iniciar_sesion(self.usuario)

        respuesta = self.client.post(f"/notificaciones/{notificacion.id}/abrir")

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], "/torneos/7")

    def test_abrir_no_redirige_fuera_del_sitio(self):
        notificacion = self.crear(self.usuario, "Sitio externo", url="https://ejemplo.com")
        self.iniciar_sesion(self.usuario)

        respuesta = self.client.post(f"/notificaciones/{notificacion.id}/abrir")

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], "/notificaciones/")

    def test_no_se_puede_tocar_una_notificacion_ajena(self):
        ajena = self.crear(self.otro, "No es tuya")
        self.iniciar_sesion(self.usuario)

        respuesta = self.client.post(
            f"/notificaciones/{ajena.id}/leer",
            headers={"Accept": "application/json"},
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.get_json(), {"error": "No autorizado."})
        db.session.refresh(ajena)
        self.assertFalse(ajena.leida)

    def test_leer_todas(self):
        self.crear(self.usuario, "Primera")
        self.crear(self.usuario, "Segunda")
        ajena = self.crear(self.otro, "Ajena")
        self.iniciar_sesion(self.usuario)

        respuesta = self.client.post(
            "/notificaciones/leer-todas", headers={"Accept": "application/json"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json(), {"ok": True, "sin_leer": 0})
        self.assertEqual(
            Notificacion.query.filter_by(usuario_id=self.usuario.id, leida=False).count(), 0
        )
        db.session.refresh(ajena)
        self.assertFalse(ajena.leida)

    def test_avisar_a_no_duplica_destinatarios(self):
        import notificaciones as notif

        creadas = notif.enviar_a(
            [self.usuario.id, self.usuario.id, self.otro.id],
            "equipo",
            "Aviso",
            "Mensaje",
        )

        self.assertEqual(len(creadas), 2)
        self.assertEqual(
            Notificacion.query.filter_by(titulo="Aviso").count(), 2
        )
        self.assertEqual(self.usuario.notificaciones[0].titulo, "Aviso")


if __name__ == "__main__":
    unittest.main()
