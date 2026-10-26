"""Migraciones incrementales para bases SQLite ya existentes."""
from sqlalchemy import text

from models import db


COLUMNAS = {
    "torneos": {
        "formato": "VARCHAR(10) NOT NULL DEFAULT ''",
        "reglas": "TEXT NOT NULL DEFAULT ''",
        "premio": "VARCHAR(200) NOT NULL DEFAULT ''",
        "total_rondas": "INTEGER",
        "iniciado_en": "DATETIME",
    },
    "inscripciones": {
        "equipo_id": "INTEGER",
    },
    "resultados": {
        "estado": "VARCHAR(20) NOT NULL DEFAULT 'confirmado'",
        "confirmado_por_id": "INTEGER",
        "resuelto_por_id": "INTEGER",
        "disputa_motivo": "VARCHAR(255)",
        "confirmado_en": "DATETIME",
    },
}

INDICES = (
    "CREATE INDEX IF NOT EXISTS ix_inscripciones_equipo_id ON inscripciones (equipo_id)",
    "CREATE INDEX IF NOT EXISTS ix_resultados_estado ON resultados (estado)",
    "CREATE INDEX IF NOT EXISTS ix_notificaciones_usuario_leida ON notificaciones (usuario_id, leida)",
)


def _columnas(tabla):
    filas = db.session.execute(text(f"PRAGMA table_info({tabla})")).fetchall()
    return {fila[1] for fila in filas}


def aplicar():
    """Agrega columnas e índices que falten. No elimina datos."""
    for tabla, columnas in COLUMNAS.items():
        existentes = _columnas(tabla)
        if not existentes:
            continue
        for nombre, definicion in columnas.items():
            if nombre not in existentes:
                db.session.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}"))
        db.session.commit()

    for sentencia in INDICES:
        db.session.execute(text(sentencia))
    db.session.commit()

    _completar_torneos()


def _completar_torneos():
    db.session.execute(text(
        """
        UPDATE torneos
        SET total_rondas = (
            SELECT MAX(partidas.ronda) FROM partidas WHERE partidas.torneo_id = torneos.id
        )
        WHERE total_rondas IS NULL
          AND EXISTS (SELECT 1 FROM partidas WHERE partidas.torneo_id = torneos.id)
        """
    ))
    db.session.execute(text(
        """
        UPDATE torneos
        SET formato = CASE
            WHEN (
                SELECT MAX(MAX(resultados.puntaje1, resultados.puntaje2))
                FROM resultados
                JOIN partidas ON partidas.id = resultados.partida_id
                WHERE partidas.torneo_id = torneos.id
            ) >= 3 THEN 'BO5'
            WHEN (
                SELECT MAX(MAX(resultados.puntaje1, resultados.puntaje2))
                FROM resultados
                JOIN partidas ON partidas.id = resultados.partida_id
                WHERE partidas.torneo_id = torneos.id
            ) >= 2 THEN 'BO3'
            ELSE 'BO1'
        END
        WHERE formato IS NULL OR formato = ''
        """
    ))
    db.session.execute(text(
        "UPDATE torneos SET formato = 'BO1' WHERE formato IS NULL OR formato = ''"
    ))
    db.session.commit()
