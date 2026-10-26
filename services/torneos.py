"""Reglas de negocio de torneos, llaves, resultados y posiciones."""
import random
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session

from database.base import ahora
from models import (
    ESTADOS_TORNEO,
    FORMATOS,
    MODALIDADES,
    Equipo,
    Inscripcion,
    Partida,
    Resultado,
    Torneo,
    Usuario,
)
from services import notificaciones as notif
from services.errors import ErrorNegocio, ErrorValidacion

OBJETIVO_MAPAS = {"BO1": 1, "BO3": 2, "BO5": 3}


def _str(datos: dict, campo: str) -> str:
    valor = datos.get(campo)
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        return ", ".join(str(item).strip() for item in valor)
    return str(valor).strip()


def _entero(valor):
    if isinstance(valor, bool):
        return None
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def _booleano(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in ("1", "true", "on", "si", "sí", "yes")


def _fecha(valor) -> datetime | None:
    if isinstance(valor, datetime):
        return valor
    texto = str(valor or "").strip().replace(" ", "T")
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def validar_datos_torneo(datos: dict, torneo: Torneo | None = None) -> dict:
    alta = torneo is None
    errores: dict = {}
    limpio: dict = {}

    def enviado(campo: str) -> bool:
        return alta or campo in datos

    if enviado("nombre"):
        nombre = _str(datos, "nombre")
        if not 3 <= len(nombre) <= 100:
            errores["nombre"] = "El nombre debe tener entre 3 y 100 caracteres."
        limpio["nombre"] = nombre

    if "descripcion" in datos or alta:
        descripcion = _str(datos, "descripcion")
        if len(descripcion) > 2000:
            errores["descripcion"] = "La descripción puede tener como máximo 2000 caracteres."
        limpio["descripcion"] = descripcion

    if "reglas" in datos or alta:
        reglas = _str(datos, "reglas")
        if len(reglas) > 5000:
            errores["reglas"] = "Las reglas pueden tener como máximo 5000 caracteres."
        limpio["reglas"] = reglas

    if "premio" in datos or alta:
        premio = _str(datos, "premio")
        if len(premio) > 200:
            errores["premio"] = "El premio puede tener como máximo 200 caracteres."
        limpio["premio"] = premio

    if enviado("videojuego"):
        videojuego = _str(datos, "videojuego")
        if not 2 <= len(videojuego) <= 80:
            errores["videojuego"] = "Indicá el videojuego (entre 2 y 80 caracteres)."
        limpio["videojuego"] = videojuego

    if enviado("fecha"):
        fecha = _fecha(datos.get("fecha"))
        if not fecha:
            errores["fecha"] = "Ingresá una fecha válida con formato AAAA-MM-DDTHH:MM."
        elif alta and fecha < ahora():
            errores["fecha"] = "La fecha del torneo no puede estar en el pasado."
        limpio["fecha"] = fecha

    if enviado("cupo_maximo"):
        cupo = _entero(datos.get("cupo_maximo"))
        if cupo is None or not 2 <= cupo <= 128:
            errores["cupo_maximo"] = "El cupo máximo debe ser un número entre 2 y 128."
        elif torneo and cupo < torneo.inscriptos:
            errores["cupo_maximo"] = (
                f"El cupo no puede ser menor a la cantidad de inscriptos ({torneo.inscriptos})."
            )
        limpio["cupo_maximo"] = cupo

    formato = _str(datos, "formato") or (torneo.formato if torneo else "BO1")
    if formato not in FORMATOS:
        errores["formato"] = "El formato debe ser BO1, BO3 o BO5."
    elif torneo and torneo.tiene_partidas and formato != torneo.formato:
        errores["formato"] = "No se puede cambiar el formato cuando ya hay partidas generadas."
    limpio["formato"] = formato

    modalidad = torneo.modalidad if torneo else "individual"
    if "modalidad" in datos:
        modalidad = _str(datos, "modalidad")
        if modalidad not in MODALIDADES:
            errores["modalidad"] = "La modalidad debe ser 'individual' o 'equipos'."
        elif torneo and torneo.inscripciones and modalidad != torneo.modalidad:
            errores["modalidad"] = "No se puede cambiar la modalidad cuando ya hay inscriptos."
        limpio["modalidad"] = modalidad

    if modalidad == "equipos":
        valor = datos.get(
            "jugadores_por_equipo",
            torneo.jugadores_por_equipo if torneo else None,
        )
        cantidad = _entero(valor)
        if cantidad is None or not 2 <= cantidad <= 10:
            errores["jugadores_por_equipo"] = (
                "En modalidad por equipos indicá entre 2 y 10 jugadores por equipo."
            )
        limpio["jugadores_por_equipo"] = cantidad
    else:
        limpio["jugadores_por_equipo"] = None

    if "estado" in datos:
        estado = _str(datos, "estado")
        estado_actual = torneo.estado if torneo else None
        if estado not in ESTADOS_TORNEO:
            errores["estado"] = "Estado inválido."
        elif estado != estado_actual and estado in ("en_curso", "finalizado"):
            errores["estado"] = (
                "Los estados 'En curso' y 'Finalizado' los asigna el sistema al iniciar "
                "el torneo y al cargar los resultados."
            )
        elif torneo and torneo.tiene_partidas and estado != estado_actual:
            errores["estado"] = (
                "El torneo ya tiene partidas generadas. Reiniciá la llave para volver a abrir "
                "inscripciones."
            )
        limpio["estado"] = estado

    if "destacado" in datos:
        limpio["destacado"] = _booleano(datos.get("destacado"))

    if errores:
        raise ErrorValidacion(errores)
    return limpio


def crear_torneo(db: Session, datos: dict, creador: Usuario) -> Torneo:
    limpio = validar_datos_torneo(datos)
    torneo = Torneo(creado_por=creador, **limpio)
    db.add(torneo)
    db.commit()
    return torneo


def actualizar_torneo(db: Session, torneo: Torneo, datos: dict) -> Torneo:
    limpio = validar_datos_torneo(datos, torneo)
    for campo, valor in limpio.items():
        setattr(torneo, campo, valor)
    db.commit()
    return torneo


def eliminar_torneo(db: Session, torneo: Torneo) -> None:
    db.delete(torneo)
    db.commit()


def buscar_torneos(
    db: Session,
    estado: str | None = None,
    videojuego: str | None = None,
    modalidad: str | None = None,
    texto: str | None = None,
) -> list[Torneo]:
    consulta = select(Torneo)
    if estado:
        if estado not in ESTADOS_TORNEO:
            raise ErrorValidacion({"estado": "Estado inválido."})
        consulta = consulta.where(Torneo.estado == estado)
    if modalidad:
        if modalidad not in MODALIDADES:
            raise ErrorValidacion({"modalidad": "Modalidad inválida."})
        consulta = consulta.where(Torneo.modalidad == modalidad)
    if videojuego:
        consulta = consulta.where(Torneo.videojuego.ilike(f"%{videojuego}%"))
    if texto:
        consulta = consulta.where(
            Torneo.nombre.ilike(f"%{texto}%")
            | Torneo.descripcion.ilike(f"%{texto}%")
        )
    return list(db.scalars(consulta.order_by(Torneo.fecha.asc())).all())


def videojuegos_disponibles(db: Session) -> list[str]:
    return list(
        db.scalars(select(Torneo.videojuego).distinct().order_by(Torneo.videojuego)).all()
    )


def _validar_equipo_inscripcion(torneo: Torneo, equipo: Equipo | None, usuario: Usuario) -> None:
    if not equipo:
        raise ErrorValidacion({"equipo_id": "Elegí un equipo para inscribirte."})
    if not equipo.es_capitan(usuario):
        raise ErrorNegocio("Solo el capitán puede inscribir al equipo.", 403)
    if not equipo.miembro_activo(usuario.id):
        raise ErrorNegocio("El capitán no pertenece al equipo.", 409)
    if len(equipo.miembros_activos) != torneo.jugadores_por_equipo:
        raise ErrorNegocio(
            f"El equipo necesita {torneo.jugadores_por_equipo} integrantes activos "
            f"(tiene {len(equipo.miembros_activos)}).",
            409,
        )
    ids_equipo = {m.usuario_id for m in equipo.miembros_activos}
    for inscripcion in torneo.inscripciones:
        if inscripcion.equipo_id == equipo.id:
            raise ErrorNegocio("Ese equipo ya está inscripto en el torneo.", 409)
        ids_inscriptos = {jugador.id for jugador in inscripcion.roster}
        repetidos = ids_equipo & ids_inscriptos
        if repetidos:
            nombres = ", ".join(
                m.usuario.username
                for m in equipo.miembros_activos
                if m.usuario_id in repetidos
            )
            raise ErrorNegocio(
                f"Estos jugadores ya están inscriptos con otro equipo: {nombres}.",
                409,
            )


def inscribir(
    db: Session, torneo: Torneo, usuario: Usuario, datos: dict | None = None
) -> Inscripcion:
    datos = datos or {}
    if torneo.estado != "inscripciones_abiertas":
        raise ErrorNegocio("Las inscripciones para este torneo no están abiertas.", 409)
    if torneo.inscripcion_de(usuario):
        raise ErrorNegocio("Ya estás inscripto en este torneo.", 409)
    if torneo.esta_completo:
        raise ErrorNegocio("El torneo está completo: no quedan cupos disponibles.", 409)

    equipo = None
    nombre_equipo = integrantes = None
    if torneo.es_por_equipos:
        equipo_id = _entero(datos.get("equipo_id"))
        equipo = db.get(Equipo, equipo_id) if equipo_id else None
        _validar_equipo_inscripcion(torneo, equipo, usuario)
        nombre_equipo = equipo.nombre
        integrantes = ", ".join(m.usuario.username for m in equipo.miembros_activos)

    inscripcion = Inscripcion(
        torneo=torneo,
        usuario=usuario,
        equipo=equipo,
        nombre_equipo=nombre_equipo,
        integrantes=integrantes,
    )
    db.add(inscripcion)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ErrorNegocio("Ya existe una inscripción igual en este torneo.", 409)

    notif.enviar_a(
        db,
        [integrante.id for integrante in inscripcion.roster],
        "inscripcion",
        "Inscripción confirmada",
        f"Quedaste inscripto en «{torneo.nombre}».",
        url=notif.url_torneo(torneo),
        torneo_id=torneo.id,
    )
    return inscripcion


def _verificar_puede_desinscribir(torneo: Torneo) -> None:
    if torneo.tiene_partidas or torneo.estado not in (
        "proximamente",
        "inscripciones_abiertas",
    ):
        raise ErrorNegocio(
            "No se puede cancelar la inscripción porque el torneo ya comenzó.", 409
        )


def cancelar_inscripcion(db: Session, torneo: Torneo, usuario: Usuario) -> None:
    inscripcion = torneo.inscripcion_de(usuario)
    if not inscripcion:
        raise ErrorNegocio("No estás inscripto en este torneo.", 404)
    if inscripcion.equipo and not inscripcion.es_capitan(usuario):
        raise ErrorNegocio(
            "Solo el capitán puede cancelar la inscripción del equipo.", 403
        )
    _verificar_puede_desinscribir(torneo)
    db.delete(inscripcion)
    db.commit()


def eliminar_inscripcion(db: Session, inscripcion: Inscripcion) -> None:
    _verificar_puede_desinscribir(inscripcion.torneo)
    db.delete(inscripcion)
    db.commit()


def _siguiente_potencia(cantidad: int) -> tuple[int, int]:
    potencia = 1
    rondas = 0
    while potencia < cantidad:
        potencia *= 2
        rondas += 1
    return potencia, rondas


def _indices_byes(cantidad_partidas: int, cantidad_byes: int) -> set[int]:
    indices: set[int] = set()
    if not cantidad_byes:
        return indices
    for i in range(cantidad_byes):
        indice = int((i + 0.5) * cantidad_partidas / cantidad_byes)
        while indice in indices:
            indice = (indice + 1) % cantidad_partidas
        indices.add(indice)
    return indices


def iniciar_torneo(db: Session, torneo: Torneo) -> Torneo:
    if torneo.estado != "inscripciones_abiertas":
        raise ErrorNegocio(
            "El torneo debe estar en inscripciones abiertas para iniciar.", 409
        )
    if len(torneo.inscripciones) < 2:
        raise ErrorNegocio("Se necesitan al menos 2 inscriptos para iniciar el torneo.", 409)
    if torneo.tiene_partidas:
        raise ErrorNegocio("Las partidas ya fueron generadas para este torneo.", 409)

    inscripciones = list(torneo.inscripciones)
    random.shuffle(inscripciones)
    tamano, total_rondas = _siguiente_potencia(len(inscripciones))
    partidas_ronda_1 = tamano // 2
    byes = tamano - len(inscripciones)
    indices_byes = _indices_byes(partidas_ronda_1, byes)

    torneo.estado = "en_curso"
    torneo.total_rondas = total_rondas
    torneo.iniciado_en = ahora()

    jugador = 0
    byes_creados: list[Partida] = []
    for indice in range(partidas_ronda_1):
        if indice in indices_byes:
            participante1 = inscripciones[jugador]
            jugador += 1
            participante2 = None
            estado = "bye"
        else:
            participante1 = inscripciones[jugador]
            participante2 = inscripciones[jugador + 1]
            jugador += 2
            estado = "pendiente"
        partida = Partida(
            ronda=1,
            numero=indice + 1,
            participante1_id=participante1.id,
            participante2_id=participante2.id if participante2 else None,
            estado=estado,
        )
        if participante2 is None:
            partida.ganador_id = participante1.id
            byes_creados.append(partida)
        torneo.partidas.append(partida)

    for ronda in range(2, total_rondas + 1):
        cantidad = tamano // (2**ronda)
        for numero in range(1, cantidad + 1):
            torneo.partidas.append(
                Partida(ronda=ronda, numero=numero, estado="pendiente")
            )
    db.flush()

    for partida in byes_creados:
        _avanzar_ganador(torneo, partida, partida.ganador_id)
    db.commit()

    notif.avisar_torneo(
        db,
        torneo,
        "torneo",
        "Torneo iniciado",
        f"«{torneo.nombre}» ya está en marcha.",
        excluir=[],
    )
    for partida in torneo.partidas:
        if partida.ronda != 1:
            continue
        if partida.estado == "bye":
            notif.avisar_partida(
                db,
                partida,
                "bye",
                "Pase directo",
                f"Pasaste directo en {torneo.nombre}. Tu próximo rival se define en la ronda siguiente.",
            )
        elif partida.lista_para_jugar:
            notif.avisar_partida(
                db,
                partida,
                "partida",
                "Te toca jugar",
                f"{partida.nombre_ronda} · Partida #{partida.numero} en «{torneo.nombre}».",
            )
    return torneo


def _validar_marcador(formato: str, puntaje1: int, puntaje2: int) -> str | None:
    objetivo = OBJETIVO_MAPAS.get(formato, 1)
    if max(puntaje1, puntaje2) != objetivo or min(puntaje1, puntaje2) >= objetivo:
        return (
            f"Para {formato} el ganador debe llegar a {objetivo} mapas y el perdedor "
            f"no puede llegar a {objetivo}."
        )
    return None


def _validar_puntajes(torneo: Torneo, datos: dict) -> tuple[int, int]:
    puntaje1 = _entero(datos.get("puntaje1"))
    puntaje2 = _entero(datos.get("puntaje2"))
    errores: dict = {}
    if puntaje1 is None or puntaje1 < 0:
        errores["puntaje1"] = "Ingresá un marcador válido para el primer participante."
    if puntaje2 is None or puntaje2 < 0:
        errores["puntaje2"] = "Ingresá un marcador válido para el segundo participante."
    if puntaje1 is not None and puntaje2 is not None:
        if puntaje1 == puntaje2:
            errores["puntaje"] = "No puede haber empate: tiene que haber un ganador."
        else:
            error_formato = _validar_marcador(torneo.formato, puntaje1, puntaje2)
            if error_formato:
                errores["formato"] = error_formato
    if errores:
        raise ErrorValidacion(errores)
    return puntaje1, puntaje2


def _finalizar_partida(torneo: Torneo, partida: Partida, ganador_id: int) -> None:
    partida.ganador_id = ganador_id
    partida.estado = "finalizada"
    db_session = object_session(partida)
    if db_session:
        db_session.flush()
    _avanzar_ganador(torneo, partida, ganador_id)
    if partida.ronda == torneo.total_rondas:
        torneo.estado = "finalizado"
    if db_session:
        db_session.flush()


def _avanzar_ganador(torneo: Torneo, partida_actual: Partida, ganador_id: int) -> None:
    total = torneo.total_rondas or max((p.ronda for p in torneo.partidas), default=0)
    if partida_actual.ronda >= total:
        return
    siguiente_numero = (partida_actual.numero + 1) // 2
    siguiente = next(
        (
            partida
            for partida in torneo.partidas
            if partida.ronda == partida_actual.ronda + 1
            and partida.numero == siguiente_numero
        ),
        None,
    )
    db_session = object_session(torneo)
    if not siguiente:
        siguiente = Partida(
            ronda=partida_actual.ronda + 1,
            numero=siguiente_numero,
            estado="pendiente",
        )
        torneo.partidas.append(siguiente)
        if db_session:
            db_session.flush()
    if partida_actual.numero % 2 == 1:
        siguiente.participante1_id = ganador_id
    else:
        siguiente.participante2_id = ganador_id
    if (
        siguiente.participante1_id
        and siguiente.participante2_id
        and siguiente.estado != "bye"
    ):
        siguiente.estado = "pendiente"


def _notificar_resultado_confirmado(
    db: Session, torneo: Torneo, partida: Partida, ganador: Inscripcion
) -> None:
    perdedor = (
        partida.participante2
        if partida.participante1_id == ganador.id
        else partida.participante1
    )
    notif.avisar_partida(
        db,
        partida,
        "resultado",
        "Resultado confirmado",
        f"{partida.nombre_ronda}: {ganador.nombre_mostrar} ganó la partida #{partida.numero}.",
    )
    if partida.ronda == torneo.total_rondas:
        notif.enviar_a(
            db,
            notif.ids_de_inscripcion(ganador),
            "campeon",
            "¡Campeón!",
            f"Ganaste «{torneo.nombre}».",
            url=notif.url_torneo(torneo),
            torneo_id=torneo.id,
        )
        return
    if perdedor:
        notif.enviar_a(
            db,
            notif.ids_de_inscripcion(perdedor),
            "eliminado",
            "Quedaste eliminado",
            f"Tu participación en «{torneo.nombre}» terminó en {partida.nombre_ronda}.",
            url=notif.url_torneo(torneo),
            torneo_id=torneo.id,
        )
    siguiente = next(
        (
            candidata
            for candidata in torneo.partidas
            if candidata.ronda == partida.ronda + 1
            and candidata.numero == (partida.numero + 1) // 2
        ),
        None,
    )
    if siguiente and siguiente.lista_para_jugar and not siguiente.resultado:
        notif.avisar_partida(
            db,
            siguiente,
            "partida",
            "Te toca jugar",
            f"Ya está definido tu rival de {siguiente.nombre_ronda} en «{torneo.nombre}».",
        )


def registrar_resultado_partida(
    db: Session,
    torneo: Torneo,
    partida_id: int,
    datos: dict,
    registrado_por: Usuario | None,
) -> Partida:
    partida = db.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if partida.estado == "finalizada":
        raise ErrorNegocio("Esta partida ya tiene un resultado confirmado.", 409)
    if partida.estado == "bye":
        raise ErrorNegocio("Las partidas de pase directo no requieren resultado.", 409)
    if partida.resultado:
        raise ErrorNegocio("Ya hay un resultado cargado para esta partida.", 409)
    if not partida.lista_para_jugar:
        raise ErrorNegocio("La partida todavía no está completa.", 409)
    if registrado_por is not None and not partida.puede_reportar(registrado_por):
        raise ErrorNegocio("No podés cargar el resultado de esta partida.", 403)

    puntaje1, puntaje2 = _validar_puntajes(torneo, datos)
    ganador_id = (
        partida.participante1_id if puntaje1 > puntaje2 else partida.participante2_id
    )
    es_admin = bool(registrado_por and registrado_por.es_admin)
    confirmado = registrado_por is None or es_admin

    resultado = Resultado(
        partida_id=partida.id,
        puntaje1=puntaje1,
        puntaje2=puntaje2,
        ganador_id=ganador_id,
        estado="confirmado" if confirmado else "pendiente",
        registrado_por_id=registrado_por.id if registrado_por else None,
        confirmado_por_id=registrado_por.id if confirmado and registrado_por else None,
        confirmado_en=ahora() if confirmado else None,
    )
    partida.resultado = resultado
    if confirmado:
        _finalizar_partida(torneo, partida, ganador_id)
    db.commit()

    if confirmado:
        _notificar_resultado_confirmado(db, torneo, partida, partida.ganador)
    else:
        notif.avisar_partida(
            db,
            partida,
            "resultado_pendiente",
            "Resultado cargado",
            f"{registrado_por.username} cargó {puntaje1}-{puntaje2}. Falta la confirmación del rival.",
        )
    return partida


def confirmar_resultado(
    db: Session, torneo: Torneo, partida_id: int, usuario: Usuario
) -> Partida:
    partida = db.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if not partida.puede_confirmar(usuario):
        raise ErrorNegocio("No podés confirmar este resultado.", 403)
    resultado = partida.resultado
    resultado.estado = "confirmado"
    resultado.confirmado_por_id = usuario.id
    resultado.confirmado_en = ahora()
    resultado.actualizado_en = ahora()
    _finalizar_partida(torneo, partida, resultado.ganador_id)
    db.commit()
    _notificar_resultado_confirmado(db, torneo, partida, partida.ganador)
    return partida


def disputar_resultado(
    db: Session, torneo: Torneo, partida_id: int, datos: dict, usuario: Usuario
) -> Partida:
    partida = db.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if not partida.puede_disputar(usuario):
        raise ErrorNegocio("No podés disputar este resultado.", 403)
    motivo = _str(datos, "motivo")
    if not 3 <= len(motivo) <= 255:
        raise ErrorValidacion(
            {"motivo": "Contá el motivo de la disputa (entre 3 y 255 caracteres)."}
        )
    partida.resultado.estado = "disputa"
    partida.resultado.disputa_motivo = motivo
    partida.resultado.actualizado_en = ahora()
    db.commit()
    notif.avisar_partida(
        db,
        partida,
        "disputa",
        "Resultado en disputa",
        f"{usuario.username} disputó la partida #{partida.numero}: {motivo}",
    )
    notif.enviar_a(
        db,
        notif.ids_admins(db),
        "disputa",
        "Disputa para resolver",
        f"Partida #{partida.numero} de «{torneo.nombre}»: {motivo}",
        url=notif.url_partida(partida),
        torneo_id=torneo.id,
    )
    return partida


def resolver_disputa(
    db: Session, torneo: Torneo, partida_id: int, datos: dict, admin: Usuario
) -> Partida:
    partida = db.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if not partida.puede_resolver(admin):
        raise ErrorNegocio("Solo un administrador puede resolver este resultado.", 403)
    puntaje1, puntaje2 = _validar_puntajes(torneo, datos)
    ganador_id = (
        partida.participante1_id if puntaje1 > puntaje2 else partida.participante2_id
    )
    resultado = partida.resultado
    resultado.puntaje1 = puntaje1
    resultado.puntaje2 = puntaje2
    resultado.ganador_id = ganador_id
    resultado.estado = "confirmado"
    resultado.confirmado_por_id = admin.id
    resultado.resuelto_por_id = admin.id
    resultado.confirmado_en = ahora()
    resultado.actualizado_en = ahora()
    _finalizar_partida(torneo, partida, ganador_id)
    db.commit()
    _notificar_resultado_confirmado(db, torneo, partida, partida.ganador)
    return partida


def rechazar_resultado(
    db: Session, torneo: Torneo, partida_id: int, admin: Usuario
) -> Partida:
    partida = db.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if not partida.puede_rechazar(admin):
        raise ErrorNegocio("Solo un administrador puede rechazar este resultado.", 403)
    partida.resultado = None
    partida.ganador_id = None
    partida.estado = "pendiente"
    db.commit()
    notif.avisar_partida(
        db,
        partida,
        "resultado_rechazado",
        "Resultado rechazado",
        f"El administrador rechazó el marcador de la partida #{partida.numero}. Carguen uno nuevo.",
    )
    return partida


def programar_partida(
    db: Session, torneo: Torneo, partida_id: int, fecha, admin: Usuario
) -> Partida:
    partida = db.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if not admin.es_admin:
        raise ErrorNegocio("Solo un administrador puede programar la partida.", 403)
    fecha_dt = _fecha(fecha)
    if not fecha_dt:
        raise ErrorValidacion({"fecha_programada": "Ingresá una fecha válida."})
    partida.fecha_programada = fecha_dt
    db.commit()
    if partida.lista_para_jugar:
        notif.avisar_partida(
            db,
            partida,
            "horario",
            "Horario definido",
            f"Partida #{partida.numero}: {fecha_dt.strftime('%d/%m/%Y %H:%M')}.",
        )
    return partida


def reiniciar_llave(db: Session, torneo: Torneo, admin: Usuario) -> Torneo:
    if not admin.es_admin:
        raise ErrorNegocio("Solo un administrador puede reiniciar la llave.", 403)
    torneo.partidas.clear()
    torneo.estado = "inscripciones_abiertas"
    torneo.total_rondas = None
    torneo.iniciado_en = None
    db.commit()
    notif.avisar_torneo(
        db,
        torneo,
        "torneo",
        "Llave reiniciada",
        f"El administrador reinició «{torneo.nombre}». Las inscripciones vuelven a estar abiertas.",
    )
    return torneo


def tabla_posiciones(torneo: Torneo) -> list[dict]:
    filas: dict[int, dict] = {}
    for inscripcion in torneo.inscripciones:
        filas[inscripcion.id] = {
            "inscripcion_id": inscripcion.id,
            "nombre": inscripcion.nombre_mostrar,
            "equipo": inscripcion.nombre_equipo,
            "usuario_id": inscripcion.usuario_id,
            "victorias": 0,
            "derrotas": 0,
            "partidas_jugadas": 0,
            "mapas_favor": 0,
            "mapas_contra": 0,
            "diferencia": 0,
            "winrate": 0,
            "racha": [],
            "estado": "En juego" if torneo.estado == "en_curso" else "Inscripto",
        }

    for partida in sorted(torneo.partidas, key=lambda p: (p.ronda, p.numero)):
        if partida.estado != "finalizada" or not partida.resultado:
            continue
        if partida.resultado.estado != "confirmado":
            continue
        for inscripcion, favor, contra in (
            (
                partida.participante1,
                partida.resultado.puntaje1,
                partida.resultado.puntaje2,
            ),
            (
                partida.participante2,
                partida.resultado.puntaje2,
                partida.resultado.puntaje1,
            ),
        ):
            if not inscripcion or inscripcion.id not in filas:
                continue
            fila = filas[inscripcion.id]
            fila["partidas_jugadas"] += 1
            fila["mapas_favor"] += favor
            fila["mapas_contra"] += contra
            if partida.ganador_id == inscripcion.id:
                fila["victorias"] += 1
                fila["racha"].append("G")
            else:
                fila["derrotas"] += 1
                fila["racha"].append("P")
                fila["estado"] = "Eliminado"

    campeon = torneo.campeon
    tabla = list(filas.values())
    for fila in tabla:
        fila["diferencia"] = fila["mapas_favor"] - fila["mapas_contra"]
        fila["winrate"] = (
            round(fila["victorias"] * 100 / fila["partidas_jugadas"])
            if fila["partidas_jugadas"]
            else 0
        )
        fila["ultimos"] = "".join(fila["racha"][-5:])
        if campeon and campeon.id == fila["inscripcion_id"]:
            fila["estado"] = "Campeón"
    tabla.sort(
        key=lambda fila: (
            -fila["victorias"],
            -fila["diferencia"],
            fila["derrotas"],
            -fila["winrate"],
            fila["nombre"].lower(),
        )
    )
    for posicion, fila in enumerate(tabla, 1):
        fila["posicion"] = posicion
    return tabla


def mi_partida(torneo: Torneo, usuario: Usuario | None) -> Partida | None:
    if not usuario:
        return None
    inscripcion = torneo.inscripcion_de(usuario)
    if not inscripcion:
        return None
    candidatas = [
        partida
        for partida in torneo.partidas
        if partida.estado == "pendiente"
        and inscripcion.id
        in (partida.participante1_id, partida.participante2_id)
    ]
    candidatas.sort(key=lambda p: (not p.lista_para_jugar, p.ronda, p.numero))
    return candidatas[0] if candidatas else None


def estadisticas(db: Session) -> dict:
    por_estado = dict(
        db.execute(
            select(Torneo.estado, func.count(Torneo.id)).group_by(Torneo.estado)
        ).all()
    )
    return {
        "usuarios": db.scalar(select(func.count(Usuario.id))) or 0,
        "torneos": db.scalar(select(func.count(Torneo.id))) or 0,
        "torneos_por_estado": {
            clave: por_estado.get(clave, 0) for clave in ESTADOS_TORNEO
        },
        "inscripciones": db.scalar(select(func.count(Inscripcion.id))) or 0,
    }
