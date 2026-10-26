"""Preparación de partidas en un servidor de CS2 por RCON."""
from .rcon import enviar_comandos


def _nombre(inscripcion):
    return inscripcion.nombre_mostrar if inscripcion else "Por definir"


def preparar_partida(servidor, partida):
    comandos = [
        'hostname "ArenaGG"',
        "mp_warmup_end",
        "mp_restartgame 1",
        "mp_freezetime 15",
        "mp_maxrounds 24",
        "mp_timelimit 0",
        f'say "[ArenaGG] {_nombre(partida.participante1)} vs {_nombre(partida.participante2)}"',
        f'say "[ArenaGG] {partida.nombre_ronda} - Partida #{partida.numero}"',
    ]
    exitos, errores = enviar_comandos(
        servidor.ip, servidor.puerto, servidor.rcon_password, comandos
    )
    return {"comandos_enviados": len(exitos), "errores": errores}
