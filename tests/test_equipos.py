"""Pruebas de equipos, roster, invitaciones y capitanía."""
import unittest

import equipos as eq
import services as sv
from models import EquipoMiembro, Notificacion, db
from tests.base import BaseTestCase


class EquiposTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.capitan = self.crear_usuario("capitan")
        self.jugador = self.crear_usuario("jugador")
        self.otro = self.crear_usuario("otro")

    def crear_equipo(self, nombre="Night Owls", capitan=None, integrantes=()):
        capitan = capitan or self.capitan
        equipo = eq.crear_equipo(
            {"nombre": nombre, "tag": nombre[:3], "descripcion": "Equipo de prueba"}, capitan
        )
        for jugador in integrantes:
            invitacion = eq.invitar(equipo, jugador.username, capitan)
            eq.responder_invitacion(invitacion, jugador, True)
        return equipo

    def test_crear_equipo_deja_al_capitan_activo(self):
        equipo = self.crear_equipo()

        self.assertEqual(equipo.capitan_id, self.capitan.id)
        self.assertEqual(len(equipo.miembros_activos), 1)
        self.assertTrue(equipo.miembro_activo(self.capitan.id))
        self.assertEqual([e.id for e in eq.equipos_de(self.capitan)], [equipo.id])
        self.assertEqual(equipo.iniciales, "NO")

    def test_nombre_repetido_no_distingue_mayusculas(self):
        self.crear_equipo("Night Owls")

        with self.assertRaises(sv.ErrorValidacion) as contexto:
            eq.crear_equipo({"nombre": "night owls"}, self.otro)
        self.assertIn("nombre", contexto.exception.errores)

    def test_invitacion_aceptada_y_notificaciones(self):
        equipo = self.crear_equipo()

        invitacion = eq.invitar(equipo, "JUGADOR", self.capitan)
        self.assertEqual(invitacion.estado, "invitado")
        self.assertEqual([i.id for i in eq.invitaciones_de(self.jugador)], [invitacion.id])
        aviso = Notificacion.query.filter_by(
            usuario_id=self.jugador.id, tipo="equipo"
        ).first()
        self.assertIsNotNone(aviso)
        self.assertIn(equipo.nombre, aviso.mensaje)

        eq.responder_invitacion(invitacion, self.jugador, True)
        db.session.expire_all()
        self.assertEqual(invitacion.estado, "activo")
        self.assertTrue(equipo.miembro_activo(self.jugador.id))
        self.assertEqual(eq.invitaciones_de(self.jugador), [])

        respuesta = Notificacion.query.filter_by(
            usuario_id=self.capitan.id, tipo="equipo"
        ).order_by(Notificacion.id.desc()).first()
        self.assertIn(self.jugador.username, respuesta.mensaje)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.responder_invitacion(invitacion, self.jugador, True)
        self.assertEqual(contexto.exception.codigo, 409)

    def test_invitacion_rechazada(self):
        equipo = self.crear_equipo()
        invitacion = eq.invitar(equipo, "jugador", self.capitan)

        eq.responder_invitacion(invitacion, self.jugador, False)
        db.session.expire_all()
        self.assertEqual(invitacion.estado, "rechazado")
        self.assertFalse(equipo.miembro_activo(self.jugador.id))

    def test_solo_el_capitan_invita(self):
        equipo = self.crear_equipo()

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.invitar(equipo, "otro", self.jugador)
        self.assertEqual(contexto.exception.codigo, 403)

    def test_invitaciones_invalidas(self):
        equipo = self.crear_equipo()

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.invitar(equipo, "noexiste", self.capitan)
        self.assertEqual(contexto.exception.codigo, 404)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.invitar(equipo, self.capitan.username, self.capitan)
        self.assertEqual(contexto.exception.codigo, 409)

        eq.invitar(equipo, "jugador", self.capitan)
        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.invitar(equipo, "jugador", self.capitan)
        self.assertEqual(contexto.exception.codigo, 409)

    def test_roster_bloqueado_con_torneo_activo(self):
        equipo = self.crear_equipo(integrantes=[self.jugador])
        torneo = self.crear_torneo(
            self.crear_usuario("admin_eq", rol="admin"),
            nombre="Copa por equipos",
            modalidad="equipos",
            cupo=4,
            jugadores_por_equipo=2,
        )
        self.inscribir(torneo, self.capitan, equipo_id=equipo.id)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.invitar(equipo, "otro", self.capitan)
        self.assertEqual(contexto.exception.codigo, 409)

        membresia = equipo.membresia_de(self.jugador.id)
        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.expulsar(equipo, membresia.id, self.capitan)
        self.assertEqual(contexto.exception.codigo, 409)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.salir(equipo, self.jugador)
        self.assertEqual(contexto.exception.codigo, 409)

        sv.cancelar_inscripcion(torneo, self.capitan)
        eq.invitar(equipo, "otro", self.capitan)
        self.assertEqual(equipo.membresia_de(self.otro.id).estado, "invitado")

    def test_transferir_capitan(self):
        equipo = self.crear_equipo(integrantes=[self.jugador])

        with self.assertRaises(sv.ErrorNegocio):
            eq.transferir_capitan(equipo, self.otro.id, self.capitan)

        eq.transferir_capitan(equipo, self.jugador.id, self.capitan)
        db.session.expire_all()
        self.assertEqual(equipo.capitan_id, self.jugador.id)
        self.assertEqual(equipo.membresia_de(self.capitan.id).rol, "jugador")
        self.assertEqual(equipo.membresia_de(self.jugador.id).rol, "capitan")

        aviso = Notificacion.query.filter_by(
            usuario_id=self.jugador.id, tipo="equipo"
        ).order_by(Notificacion.id.desc()).first()
        self.assertIn("capitán", aviso.titulo)

        with self.assertRaises(sv.ErrorNegocio):
            eq.invitar(equipo, "otro", self.capitan)
        eq.invitar(equipo, "otro", self.jugador)

    def test_capitan_no_puede_salir_ni_ser_expulsado(self):
        equipo = self.crear_equipo(integrantes=[self.jugador])
        membresia_capitan = equipo.membresia_de(self.capitan.id)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.salir(equipo, self.capitan)
        self.assertEqual(contexto.exception.codigo, 409)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.expulsar(equipo, membresia_capitan.id, self.capitan)
        self.assertEqual(contexto.exception.codigo, 409)

    def test_salir_del_equipo(self):
        equipo = self.crear_equipo(integrantes=[self.jugador])

        eq.salir(equipo, self.jugador)
        db.session.expire_all()
        self.assertFalse(equipo.miembro_activo(self.jugador.id))
        self.assertEqual(eq.equipos_de(self.jugador), [])

        aviso = Notificacion.query.filter_by(
            usuario_id=self.capitan.id, tipo="equipo"
        ).order_by(Notificacion.id.desc()).first()
        self.assertIn(self.jugador.username, aviso.mensaje)

    def test_equipo_completo_para_inscribir(self):
        equipo = self.crear_equipo()
        torneo = self.crear_torneo(
            self.crear_usuario("admin_roster", rol="admin"),
            nombre="Copa 2v2",
            modalidad="equipos",
            cupo=4,
            jugadores_por_equipo=2,
        )

        self.assertEqual(eq.equipos_para_torneo(torneo, self.capitan), [])
        with self.assertRaises(sv.ErrorNegocio) as contexto:
            self.inscribir(torneo, self.capitan, equipo_id=equipo.id)
        self.assertEqual(contexto.exception.codigo, 409)

        invitacion = eq.invitar(equipo, "jugador", self.capitan)
        eq.responder_invitacion(invitacion, self.jugador, True)
        self.assertEqual(eq.equipos_para_torneo(torneo, self.capitan), [equipo])

        self.inscribir(torneo, self.capitan, equipo_id=equipo.id)
        self.assertIsNotNone(eq.inscripcion_de(equipo, torneo))

    def test_jugador_repetido_en_dos_equipos(self):
        admin = self.crear_usuario("admin_dup", rol="admin")
        equipo_a = self.crear_equipo("Alpha", integrantes=[self.jugador])
        equipo_b = self.crear_equipo("Beta", capitan=self.otro, integrantes=[self.jugador])
        torneo = self.crear_torneo(
            admin,
            nombre="Copa duplicados",
            modalidad="equipos",
            cupo=4,
            jugadores_por_equipo=2,
        )
        self.inscribir(torneo, self.capitan, equipo_id=equipo_a.id)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            self.inscribir(torneo, self.otro, equipo_id=equipo_b.id)
        self.assertIn(self.jugador.username, contexto.exception.mensaje)

    def test_eliminar_equipo(self):
        equipo = self.crear_equipo(integrantes=[self.jugador])

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.eliminar_equipo(equipo, self.jugador)
        self.assertEqual(contexto.exception.codigo, 403)

        membresia_id = equipo.membresia_de(self.capitan.id).id
        eq.eliminar_equipo(equipo, self.capitan)
        self.assertIsNone(db.session.get(EquipoMiembro, membresia_id))

    def test_no_se_elimina_equipo_con_inscripcion(self):
        admin = self.crear_usuario("admin_del", rol="admin")
        equipo = self.crear_equipo(integrantes=[self.jugador])
        torneo = self.crear_torneo(
            admin,
            nombre="Copa eliminación",
            modalidad="equipos",
            cupo=4,
            jugadores_por_equipo=2,
        )
        self.inscribir(torneo, self.capitan, equipo_id=equipo.id)

        with self.assertRaises(sv.ErrorNegocio) as contexto:
            eq.eliminar_equipo(equipo, self.capitan)
        self.assertEqual(contexto.exception.codigo, 409)


if __name__ == "__main__":
    unittest.main()
