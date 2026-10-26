"""Carga datos de demostración en una base vacía.

Uso:
    python seed_demo.py

Credenciales:
    admin / Admin1234
    ShadowFox, NeoBlaze, PixelQueen, Ragnar, LunaByte, Kairo, Nova, Drift, Vex, Onyx / Jugador1234
"""
from datetime import timedelta

from sqlalchemy import select

from database.base import ahora
from database.session import crear_engine, crear_fabrica_sesiones, inicializar_base
from config import get_settings
from models import Usuario
from services import equipos as equipos_sv
from services import torneos as torneos_sv
from services import usuarios as usuarios_sv

NICKS = [
    "ShadowFox",
    "NeoBlaze",
    "PixelQueen",
    "Ragnar",
    "LunaByte",
    "Kairo",
    "Nova",
    "Drift",
    "Vex",
    "Onyx",
]


def main() -> None:
    engine = crear_engine(get_settings())
    inicializar_base(engine)
    db = crear_fabrica_sesiones(engine)()

    try:
        if db.scalar(select(Usuario.id).limit(1)):
            print("La base ya tiene datos. Para regenerar la demo usá una base vacía.")
            return

        admin = usuarios_sv.registrar_usuario(
            db,
            {
                "username": "admin",
                "email": "admin@demo.com",
                "password": "Admin1234",
                "juegos_favoritos": "Valorant, Tekken 8",
            },
            rol="admin",
        )
        jugadores = [
            usuarios_sv.registrar_usuario(
                db,
                {
                    "username": nick,
                    "email": f"jugador{indice}@demo.com",
                    "password": "Jugador1234",
                    "juegos_favoritos": "Valorant, Rocket League, Counter-Strike 1.6",
                },
            )
            for indice, nick in enumerate(NICKS, start=1)
        ]
        por_nick = {jugador.username: jugador for jugador in jugadores}

        def crear_equipo(nombre: str, tag: str, capitan: Usuario, integrantes, descripcion: str):
            equipo = equipos_sv.crear_equipo(
                db,
                {"nombre": nombre, "tag": tag, "descripcion": descripcion},
                capitan,
            )
            for nick in integrantes:
                membresia = equipos_sv.invitar(db, equipo, nick, capitan)
                equipos_sv.responder_invitacion(db, membresia, por_nick[nick], True)
            return equipo

        night = crear_equipo(
            "Night Owls",
            "OWL",
            por_nick["ShadowFox"],
            ["NeoBlaze", "PixelQueen", "LunaByte", "Nova"],
            "Escuadra nocturna de Valorant. Comunicación y objetivos por encima de todo.",
        )
        dragons = crear_equipo(
            "Red Dragons",
            "RDR",
            por_nick["Ragnar"],
            ["Kairo", "Drift", "Vex", "Onyx"],
            "Cinco jugadores con experiencia en ligas amateur. Juego agresivo y rápido.",
        )

        def torneo(nombre: str, juego: str, dias: int, cupo: int, **extra):
            datos = {
                "nombre": nombre,
                "videojuego": juego,
                "cupo_maximo": cupo,
                "fecha": (ahora() + timedelta(days=dias)).isoformat(),
                "estado": "inscripciones_abiertas",
                "descripcion": f"Torneo de {juego}. Competí, ganá y sumá experiencia en la arena.",
                "premio": "A definir",
                "reglas": "Llegar 15 minutos antes. Respetar el fair play y las decisiones del staff.",
            }
            datos.update(extra)
            return torneos_sv.crear_torneo(db, datos, admin)

        rocket = torneo(
            "Rocket League Showdown",
            "Rocket League",
            5,
            8,
            formato="BO3",
            destacado=True,
            premio="$50.000 y trofeo digital",
        )
        for nick in ("ShadowFox", "NeoBlaze", "Kairo", "Onyx"):
            torneos_sv.inscribir(db, rocket, por_nick[nick], {})
        torneos_sv.iniciar_torneo(db, rocket)
        primera = next(
            partida
            for partida in rocket.partidas
            if partida.estado == "pendiente" and partida.lista_para_jugar
        )
        torneos_sv.registrar_resultado_partida(
            db, rocket, primera.id, {"puntaje1": 2, "puntaje2": 1}, admin
        )

        fc = torneo("Duelo EA FC 25", "EA FC 25", 7, 4, formato="BO1")
        for nick in ("PixelQueen", "LunaByte"):
            torneos_sv.inscribir(db, fc, por_nick[nick], {})

        valorant = torneo(
            "Valorant 5v5 Cup",
            "Valorant",
            14,
            8,
            modalidad="equipos",
            jugadores_por_equipo=5,
            formato="BO3",
            destacado=True,
            premio="$80.000 y plaza para la final anual",
        )
        torneos_sv.inscribir(db, valorant, night.capitan, {"equipo_id": night.id})
        torneos_sv.inscribir(db, valorant, dragons.capitan, {"equipo_id": dragons.id})

        torneo(
            "Street Fighter 6 Masters",
            "Street Fighter 6",
            30,
            32,
            estado="proximamente",
            formato="BO5",
        )

        invitational = torneo(
            "ArenaGG Invitational",
            "Valorant",
            1,
            4,
            formato="BO1",
            premio="Trofeo ArenaGG",
        )
        for nick in ("ShadowFox", "Kairo", "Nova", "Vex"):
            torneos_sv.inscribir(db, invitational, por_nick[nick], {})
        torneos_sv.iniciar_torneo(db, invitational)

        while True:
            partida = next(
                (
                    pendiente
                    for pendiente in sorted(
                        invitational.partidas, key=lambda item: (item.ronda, item.numero)
                    )
                    if pendiente.estado == "pendiente" and pendiente.lista_para_jugar
                ),
                None,
            )
            if not partida:
                break
            torneos_sv.registrar_resultado_partida(
                db, invitational, partida.id, {"puntaje1": 1, "puntaje2": 0}, admin
            )

        print("Datos de prueba cargados.")
        print(f"  {len(jugadores)} jugadores y 2 equipos")
        print("  5 torneos: 2 abiertos, 1 en curso, 1 próximo y 1 finalizado")
        print("  admin / Admin1234")
        print("  jugadores / Jugador1234")
    finally:
        db.close()


if __name__ == "__main__":
    main()
