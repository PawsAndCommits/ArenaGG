"""Pruebas de la migración de una base SQLite anterior."""
import os
import sqlite3
import tempfile
import unittest

from tests.base import BaseTestCase  # noqa: F401  (configura el entorno de pruebas)

import migraciones
from app import create_app
from models import db
from sqlalchemy import text


class MigracionesTest(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory(prefix="arenagg-migracion-")
        self.ruta = os.path.join(self.carpeta.name, "vieja.db")
        self.crear_base_vieja(self.ruta)
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "clave-de-pruebas",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///" + self.ruta,
                "CSRF_ENABLED": False,
                "MODO_SERVIDORES": False,
                "STEAM_API_KEY": "",
                "CS2_WEBHOOK_SECRET": "",
            }
        )
        self.contexto = self.app.app_context()
        self.contexto.push()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.contexto.pop()
        self.carpeta.cleanup()

    @staticmethod
    def crear_base_vieja(ruta):
        conexion = sqlite3.connect(ruta)
        conexion.executescript(
            """
            CREATE TABLE torneos (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                descripcion TEXT NOT NULL DEFAULT '',
                videojuego TEXT NOT NULL,
                fecha DATETIME NOT NULL,
                cupo_maximo INTEGER NOT NULL,
                estado TEXT NOT NULL DEFAULT 'proximamente',
                modalidad TEXT NOT NULL DEFAULT 'individual',
                jugadores_por_equipo INTEGER,
                destacado BOOLEAN NOT NULL DEFAULT 0,
                creado_por_id INTEGER,
                creado_en DATETIME
            );
            CREATE TABLE partidas (
                id INTEGER PRIMARY KEY,
                torneo_id INTEGER NOT NULL,
                ronda INTEGER NOT NULL,
                numero INTEGER NOT NULL
            );
            CREATE TABLE resultados (
                id INTEGER PRIMARY KEY,
                partida_id INTEGER NOT NULL,
                puntaje1 INTEGER NOT NULL,
                puntaje2 INTEGER NOT NULL,
                ganador_id INTEGER NOT NULL,
                registrado_por_id INTEGER,
                registrado_en DATETIME
            );
            CREATE TABLE inscripciones (
                id INTEGER PRIMARY KEY,
                torneo_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,
                nombre_equipo TEXT,
                integrantes TEXT,
                creado_en DATETIME
            );
            INSERT INTO torneos (id, nombre, videojuego, fecha, cupo_maximo, estado)
                VALUES (1, 'Viejo BO5', 'CS2', '2025-01-01 12:00:00', 8, 'finalizado');
            INSERT INTO torneos (id, nombre, videojuego, fecha, cupo_maximo, estado)
                VALUES (2, 'Viejo sin partidas', 'Valorant', '2025-02-01 12:00:00', 4, 'proximamente');
            INSERT INTO partidas (id, torneo_id, ronda, numero) VALUES (1, 1, 1, 1);
            INSERT INTO partidas (id, torneo_id, ronda, numero) VALUES (2, 1, 2, 1);
            INSERT INTO resultados (id, partida_id, puntaje1, puntaje2, ganador_id)
                VALUES (1, 1, 2, 0, 10);
            INSERT INTO resultados (id, partida_id, puntaje1, puntaje2, ganador_id)
                VALUES (2, 2, 3, 1, 10);
            """
        )
        conexion.commit()
        conexion.close()

    def columnas(self, tabla):
        filas = db.session.execute(text(f"PRAGMA table_info({tabla})")).fetchall()
        return {fila[1] for fila in filas}

    def test_agrega_columnas_sin_borrar_datos(self):
        self.assertTrue(
            {"formato", "reglas", "premio", "total_rondas", "iniciado_en"}
            <= self.columnas("torneos")
        )
        self.assertIn("equipo_id", self.columnas("inscripciones"))
        self.assertTrue(
            {"estado", "confirmado_por_id", "resuelto_por_id", "disputa_motivo", "confirmado_en"}
            <= self.columnas("resultados")
        )

        total = db.session.execute(text("SELECT COUNT(*) FROM torneos")).scalar()
        self.assertEqual(total, 2)

    def test_completa_rondas_y_formato_de_los_datos_existentes(self):
        fila = db.session.execute(
            text("SELECT formato, total_rondas FROM torneos WHERE id = 1")
        ).one()
        self.assertEqual(fila.formato, "BO5")
        self.assertEqual(fila.total_rondas, 2)

        fila = db.session.execute(
            text("SELECT formato, total_rondas FROM torneos WHERE id = 2")
        ).one()
        self.assertEqual(fila.formato, "BO1")
        self.assertIsNone(fila.total_rondas)

    def test_resultados_viejos_quedan_confirmados(self):
        estados = {
            fila[0]
            for fila in db.session.execute(text("SELECT estado FROM resultados")).all()
        }
        self.assertEqual(estados, {"confirmado"})

    def test_crea_los_indices(self):
        indices = {
            fila[1]
            for fila in db.session.execute(text("PRAGMA index_list(resultados)")).all()
        }
        self.assertIn("ix_resultados_estado", indices)

        indices = {
            fila[1]
            for fila in db.session.execute(text("PRAGMA index_list(notificaciones)")).all()
        }
        self.assertIn("ix_notificaciones_usuario_leida", indices)

    def test_es_idempotente(self):
        migraciones.aplicar()

        self.assertEqual(
            db.session.execute(text("SELECT COUNT(*) FROM torneos")).scalar(), 2
        )
        self.assertIn("formato", self.columnas("torneos"))


if __name__ == "__main__":
    unittest.main()
