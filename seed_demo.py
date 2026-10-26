"""Carga datos de prueba para ver la aplicación con contenido.

Uso: python seed_demo.py

    admin / Admin1234
    ShadowFox, NeoBlaze, PixelQueen, Ragnar, LunaByte, Kairo, Nova, Drift, Vex, Onyx / Jugador1234
"""
from datetime import timedelta

import equipos as eq
import services as sv
from app import app
from models import Usuario, ahora

NICKS = ["ShadowFox", "NeoBlaze", "PixelQueen", "Ragnar", "LunaByte",
         "Kairo", "Nova", "Drift", "Vex", "Onyx"]


def main():
    with app.app_context():
        if Usuario.query.first():
            print("La base ya tiene datos. Para regenerar la demo, usá una base vacía.")
            return

        admin = sv.registrar_usuario(
            {"username": "admin", "email": "admin@demo.com", "password": "Admin1234",
             "juegos_favoritos": "Valorant, Tekken 8"},
            rol="admin",
        )
        jugadores = [
            sv.registrar_usuario(
                {"username": nick, "email": f"jugador{i}@demo.com", "password": "Jugador1234",
                 "juegos_favoritos": "Valorant, Rocket League, CS2"}
            )
            for i, nick in enumerate(NICKS, start=1)
        ]
        por_nick = {jugador.username: jugador for jugador in jugadores}

        def crear_equipo(nombre, tag, capitan, integrantes, descripcion):
            equipo = eq.crear_equipo(
                {"nombre": nombre, "tag": tag, "descripcion": descripcion}, capitan
            )
            for nick in integrantes:
                invitacion = eq.invitar(equipo, nick, capitan)
                eq.responder_invitacion(invitacion, por_nick[nick], True)
            return equipo

        night = crear_equipo(
            "Night Owls", "OWL", por_nick["ShadowFox"],
            ["NeoBlaze", "PixelQueen", "LunaByte", "Nova"],
            "Escuadra nocturna de Valorant. Comunicación y objetivos por encima de todo.",
        )
        dragons = crear_equipo(
            "Red Dragons", "RDR", por_nick["Ragnar"],
            ["Kairo", "Drift", "Vex", "Onyx"],
            "Cinco jugadores con experiencia en ligas amateur. Juego agresivo y rápido.",
        )

        def torneo(nombre, juego, dias, cupo, estado="inscripciones_abiertas", destacado=False, **extra):
            return sv.crear_torneo(
                {"nombre": nombre, "videojuego": juego, "cupo_maximo": cupo,
                 "fecha": (ahora() + timedelta(days=dias)).isoformat(),
                 "estado": estado, "destacado": destacado,
                 "descripcion": f"Torneo de {juego}. Inscripciones abiertas para todos los niveles.",
                 "premio": "$50.000 y trofeo digital" if destacado else "A definir",
                 "reglas": "Llegar 15 minutos antes. Respetar el fair play y las decisiones del staff.",
                 **extra},
                admin,
            )

        rocket = torneo("Rocket League Showdown", "Rocket League", 5, 8, destacado=True, formato="BO3")
        for nick in ("ShadowFox", "NeoBlaze", "Kairo", "Onyx"):
            sv.inscribir(rocket, por_nick[nick])

        fc = torneo("Duelo EA FC 25", "EA FC 25", 7, 4, formato="BO1")
        for nick in ("PixelQueen", "LunaByte"):
            sv.inscribir(fc, por_nick[nick])

        valorant = torneo(
            "Valorant 5v5 Cup", "Valorant", 14, 8, destacado=True,
            modalidad="equipos", jugadores_por_equipo=5, formato="BO3",
        )
        sv.inscribir(valorant, night.capitan, {"equipo_id": night.id})
        sv.inscribir(valorant, dragons.capitan, {"equipo_id": dragons.id})

        torneo("Street Fighter 6 Masters", "Street Fighter 6", 30, 32, estado="proximamente", formato="BO5")
        print("Datos de prueba cargados: 10 jugadores, 2 equipos y 4 torneos.")


if __name__ == "__main__":
    main()
