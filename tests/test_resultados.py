"""Pruebas de carga, confirmación, disputa y resolución de resultados."""
import unittest

import services as sv
from models import Notificacion, db
from tests.base import BaseTestCase


class ResultadosTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin, self.jugadores, self.torneo = self.iniciar_con(2, formato="BO3")
        self.p1, self.p2 = self.jugadores
        self.partida = self.torneo.partidas[0]

    def cargar(self, jugador, puntaje1=2, puntaje2=0):
        return sv.registrar_resultado_partida(
            self.torneo,
            self.partida.id,
            {"puntaje1": puntaje1, "puntaje2": puntaje2},
            jugador,
        )

    def test_carga_de_un_capitan_queda_pendiente(self):
        self.cargar(self.p1)

        db.session.expire_all()
        self.assertEqual(self.partida.resultado.estado, "pendiente")
        self.assertEqual(self.partida.resultado.registrado_por_id, self.p1.id)
        self.assertIsNone(self.partida.resultado.confirmado_por_id)
        self.assertEqual(self.partida.estado, "pendiente")
        self.assertIsNone(self.partida.ganador_id)
        self.assertTrue(self.partida.puede_confirmar(self.p2))
        self.assertFalse(self.partida.puede_confirmar(self.p1))

        avisos = Notificacion.query.filter_by(
            usuario_id=self.p2.id, tipo="resultado_pendiente"
        ).all()
        self.assertEqual(len(avisos), 1)
        self.assertIn("2-0", avisos[0].mensaje)
        self.assertEqual(avisos[0].url, f"/torneos/{self.torneo.id}/partidas/{self.partida.id}")

    def test_el_rival_confirma_y_el_ganador_avanza(self):
        self.cargar(self.p1)
        sv.confirmar_resultado(self.torneo, self.partida.id, self.p2)

        db.session.expire_all()
        self.assertEqual(self.partida.resultado.estado, "confirmado")
        self.assertEqual(self.partida.resultado.confirmado_por_id, self.p2.id)
        self.assertEqual(self.partida.estado, "finalizada")
        self.assertEqual(self.partida.ganador_id, self.partida.participante1_id)
        self.assertEqual(self.torneo.estado, "finalizado")
        self.assertEqual(self.torneo.campeon.id, self.partida.participante1_id)

        campeon = Notificacion.query.filter_by(
            usuario_id=self.partida.participante1.usuario_id, tipo="campeon"
        ).first()
        self.assertIsNotNone(campeon)
        self.assertIn(self.torneo.nombre, campeon.mensaje)

    def test_el_autor_no_puede_confirmar_su_propio_resultado(self):
        self.cargar(self.p1)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            sv.confirmar_resultado(self.torneo, self.partida.id, self.p1)
        self.assertEqual(contexto.exception.codigo, 403)

    def test_no_se_puede_cargar_dos_veces(self):
        self.cargar(self.p1)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            self.cargar(self.p2, 0, 2)
        self.assertEqual(contexto.exception.codigo, 409)

    def test_un_admin_confirma_en_el_acto(self):
        self.cargar(self.admin, 2, 1)

        db.session.expire_all()
        self.assertEqual(self.partida.resultado.estado, "confirmado")
        self.assertEqual(self.partida.resultado.confirmado_por_id, self.admin.id)
        self.assertEqual(self.partida.estado, "finalizada")
        self.assertEqual(self.partida.ganador_id, self.partida.participante1_id)

    def test_disputa_y_resolucion_del_admin(self):
        self.cargar(self.p1)
        sv.disputar_resultado(
            self.torneo,
            self.partida.id,
            {"motivo": "El marcador real fue 1-2."},
            self.p2,
        )

        db.session.expire_all()
        self.assertEqual(self.partida.resultado.estado, "disputa")
        self.assertEqual(self.partida.resultado.disputa_motivo, "El marcador real fue 1-2.")
        self.assertEqual(self.partida.estado, "pendiente")
        self.assertTrue(self.partida.puede_resolver(self.admin))

        aviso_admin = Notificacion.query.filter_by(
            usuario_id=self.admin.id, tipo="disputa"
        ).first()
        self.assertIsNotNone(aviso_admin)
        self.assertIn(self.torneo.nombre, aviso_admin.mensaje)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            sv.resolver_disputa(
                self.torneo, self.partida.id, {"puntaje1": 0, "puntaje2": 2}, self.p2
            )
        self.assertEqual(contexto.exception.codigo, 403)

        sv.resolver_disputa(
            self.torneo, self.partida.id, {"puntaje1": 1, "puntaje2": 2}, self.admin
        )

        db.session.expire_all()
        self.assertEqual(self.partida.resultado.estado, "confirmado")
        self.assertEqual(self.partida.resultado.resuelto_por_id, self.admin.id)
        self.assertEqual(self.partida.resultado.puntaje1, 1)
        self.assertEqual(self.partida.resultado.puntaje2, 2)
        self.assertEqual(self.partida.ganador_id, self.partida.participante2_id)
        self.assertEqual(self.torneo.campeon.id, self.partida.participante2_id)

    def test_la_disputa_necesita_un_motivo(self):
        self.cargar(self.p1)

        with self.assertRaises(sv.ErrorValidacion) as contexto:
            sv.disputar_resultado(self.torneo, self.partida.id, {"motivo": "no"}, self.p2)
        self.assertIn("motivo", contexto.exception.errores)

    def test_el_admin_puede_rechazar_y_cargar_de_nuevo(self):
        self.cargar(self.p1)
        sv.rechazar_resultado(self.torneo, self.partida.id, self.admin)

        db.session.expire_all()
        self.assertIsNone(self.partida.resultado)
        self.assertEqual(self.partida.estado, "pendiente")
        self.assertIsNone(self.partida.ganador_id)

        aviso = Notificacion.query.filter_by(
            usuario_id=self.p2.id, tipo="resultado_rechazado"
        ).first()
        self.assertIsNotNone(aviso)

        self.cargar(self.p2, 0, 2)
        db.session.expire_all()
        self.assertEqual(self.partida.resultado.estado, "pendiente")
        sv.confirmar_resultado(self.torneo, self.partida.id, self.p1)
        db.session.expire_all()
        self.assertEqual(self.partida.ganador_id, self.partida.participante2_id)

    def test_marcador_fuera_del_formato(self):
        for puntajes in ((3, 0), (1, 0), (2, 2)):
            with self.subTest(puntajes=puntajes):
                with self.assertRaises(sv.ErrorValidacion):
                    self.cargar(self.p1, *puntajes)
                self.assertIsNone(self.partida.resultado)

    def test_solo_los_capitanes_cargan(self):
        otro = self.crear_usuario("intruso")
        with self.assertRaises(sv.ErrorNegocio) as contexto:
            self.cargar(otro, 2, 0)
        self.assertEqual(contexto.exception.codigo, 403)


if __name__ == "__main__":
    unittest.main()
