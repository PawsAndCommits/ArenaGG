"""Prueba de humo de los datos de demostración."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_seed_demo_genera_la_base_de_demostracion(tmp_path):
    ruta = tmp_path / "demo.db"
    entorno = os.environ.copy()
    entorno["DATABASE_URL"] = f"sqlite:///{ruta.as_posix()}"
    entorno["SECRET_KEY"] = "clave-de-pruebas"

    resultado = subprocess.run(
        [sys.executable, "seed_demo.py"],
        cwd=RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "Datos de prueba cargados." in resultado.stdout

    with sqlite3.connect(ruta) as conexion:
        usuarios = conexion.execute("select count(*) from usuarios").fetchone()[0]
        equipos = conexion.execute("select count(*) from equipos").fetchone()[0]
        torneos = conexion.execute("select count(*) from torneos").fetchone()[0]
        inscripciones = conexion.execute(
            "select count(*) from inscripciones"
        ).fetchone()[0]
        partidas = conexion.execute("select count(*) from partidas").fetchone()[0]
        estados = {
            fila[0] for fila in conexion.execute("select estado from torneos")
        }

    assert usuarios == 11
    assert equipos == 2
    assert torneos == 5
    assert inscripciones == 12
    assert partidas == 6
    assert {"inscripciones_abiertas", "en_curso", "finalizado"} <= estados
