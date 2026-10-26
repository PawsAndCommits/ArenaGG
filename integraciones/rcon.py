"""Cliente RCON para servidores de CS2."""
from mcrcon import MCRcon


class RconError(Exception):
    pass


def enviar_comando(host, puerto, password, comando, timeout=5):
    try:
        with MCRcon(host, password, port=int(puerto), timeout=timeout) as mcr:
            return mcr.command(comando)
    except Exception as error:
        raise RconError(f"{host}:{puerto} -> {error}") from error


def enviar_comandos(host, puerto, password, comandos, timeout=5):
    exitos, errores = [], []
    try:
        with MCRcon(host, password, port=int(puerto), timeout=timeout) as mcr:
            for comando in comandos:
                try:
                    exitos.append((comando, mcr.command(comando)))
                except Exception as error:
                    errores.append((comando, str(error)))
    except Exception as error:
        raise RconError(f"{host}:{puerto} -> {error}") from error
    return exitos, errores
