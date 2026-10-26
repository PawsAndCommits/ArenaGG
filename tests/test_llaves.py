"""Pruebas de generación de llaves y avance de ganadores."""
import unittest

import services as sv
from models import db
from tests.base import BaseTestCase


class LlavesTest(BaseTestCase):
    def test_llaves_desde_dos_hasta_nueve_jugadores(self):
        for cantidad in range(2, 10):
            with self.subTest(jugadores=cantidad):
                db.drop_all()
                db.create_all()
                _, _, torneo = self.iniciar_con(cantidad)

                potencia = 2 ** (cantidad - 1).bit_length()
                byes = potencia - cantidad
                primera = [p for p in torneo.partidas if p.ronda == 1]

                self.assertEqual(torneo.estado, "en_curso")
                self.assertEqual(torneo.total_rondas, (cantidad - 1).bit_length())
                self.assertEqual(len(primera), potencia // 2)
                self.assertEqual(sum(1 for p in primera if p.estado == "bye"), byes)

                participantes = []
                for partida in primera:
                    if partida.participante1_id:
                        participantes.append(partida.participante1_id)
                    if partida.participante2_id:
                        participantes.append(partida.participante2_id)
                self.assertEqual(len(participantes), cantidad)
                self.assertEqual(set(participantes), {i.id for i in torneo.inscripciones})

                for partida in primera:
                    if partida.estado == "bye":
                        self.assertIsNotNone(partida.ganador_id)
                        self.assertIsNotNone(partida.participante1_id)
                        self.assertIsNone(partida.participante2_id)
                        self.verificar_avance(torneo, partida)

                for ronda in range(2, torneo.total_rondas + 1):
                    partidas_ronda = [p for p in torneo.partidas if p.ronda == ronda]
                    self.assertEqual(len(partidas_ronda), potencia // (2 ** ronda))

    def verificar_avance(self, torneo, partida):
        siguiente_numero = (partida.numero + 1) // 2
        siguiente = next(
            p
            for p in torneo.partidas
            if p.ronda == partida.ronda + 1 and p.numero == siguiente_numero
        )
        esperado = (
            siguiente.participante1_id
            if partida.numero % 2 == 1
            else siguiente.participante2_id
        )
        self.assertEqual(esperado, partida.ganador_id)

    def test_avance_completo_hasta_el_campeon(self):
        _, jugadores, torneo = self.iniciar_con(6)

        vueltas = 0
        while torneo.estado != "finalizado":
            db.session.expire_all()
            partida = next(
                (
                    p
                    for p in torneo.partidas
                    if p.estado == "pendiente" and p.lista_para_jugar and not p.resultado
                ),
                None,
            )
            self.assertIsNotNone(partida, "No hay partida lista para avanzar")
            sv.registrar_resultado_partida(
                torneo, partida.id, {"puntaje1": 1, "puntaje2": 0}, None
            )
            vueltas += 1
            self.assertLess(vueltas, 20)

        db.session.expire_all()
        self.assertIsNotNone(torneo.campeon)
        self.assertEqual(torneo.estado, "finalizado")
        tabla = sv.tabla_posiciones(torneo)
        campeon = next(f for f in tabla if f["estado"] == "Campeón")
        self.assertEqual(campeon["inscripcion_id"], torneo.campeon.id)
        self.assertEqual(campeon["derrotas"], 0)
        eliminados = [f for f in tabla if f["estado"] == "Eliminado"]
        self.assertEqual(len(eliminados), 5)

    def test_marcador_estricto_segun_formato(self):
        _, _, torneo = self.iniciar_con(2, formato="BO3")
        partida = torneo.partidas[0]

        with self.assertRaises(sv.ErrorValidacion):
            sv.registrar_resultado_partida(
                torneo, partida.id, {"puntaje1": 1, "puntaje2": 0}, None
            )
        with self.assertRaises(sv.ErrorValidacion):
            sv.registrar_resultado_partida(
                torneo, partida.id, {"puntaje1": 2, "puntaje2": 2}, None
            )
        sv.registrar_resultado_partida(
            torneo, partida.id, {"puntaje1": 2, "puntaje2": 1}, None
        )
        self.assertEqual(partida.estado, "finalizada")
        self.assertEqual(torneo.estado, "finalizado")

    def test_no_se_puede_iniciar_con_un_jugador(self):
        admin = self.crear_usuario("admin_solo", rol="admin")
        jugador = self.crear_usuario("jugador_solo")
        torneo = self.crear_torneo(admin, nombre="Individual", cupo=4)
        self.inscribir(torneo, jugador)
        with self.assertRaises(sv.ErrorNegocio):
            sv.iniciar_torneo(torneo)


if __name__ == "__main__":
    unittest.main()
