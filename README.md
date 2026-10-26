# ArenaGG

Plataforma de torneos de esports con inscripciones, equipos, llaves de eliminación directa, resultados confirmados por los capitanes, posiciones y notificaciones. Backend en FastAPI con SQLAlchemy 2, Pydantic y JWT; frontend en JavaScript vanilla que consume la API por HTTP.

## Qué incluye

- Registro, login y perfiles con autenticación JWT.
- Torneos individuales y por equipos, con formato BO1, BO3 o BO5.
- Equipos con tag, roster, invitaciones y capitanía transferible.
- Inscripción individual o del equipo completo, con control de cupos y bloqueo de roster.
- Llaves de eliminación directa con pases directos cuando el cupo no es potencia de dos.
- Sala de partida con marcador, rosters y estado del resultado.
- El capitán carga el marcador, el rival lo confirma o lo disputa y el admin resuelve.
- Tabla de posiciones con victorias, diferencia de mapas, winrate y racha.
- Historial de torneos por jugador y estadísticas públicas.
- Notificaciones persistidas, consultadas por polling cada 20 segundos.
- Documentación interactiva de la API en `/docs`.

## Requisitos

- Python 3.11 o superior
- pip

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Editá `.env` y cambiá `SECRET_KEY`. La base SQLite se crea automáticamente la primera vez que arranca la aplicación, con las tablas de la versión actual.

## Datos de prueba

Con la base vacía:

```powershell
python seed_demo.py
```

Crea un administrador, diez jugadores, dos equipos y cinco torneos en distintos estados.

| Usuario | Contraseña |
|---|---|
| `admin` | `Admin1234` |
| `ShadowFox`, `NeoBlaze`, `PixelQueen`, `Ragnar`, `LunaByte`, `Kairo`, `Nova`, `Drift`, `Vex`, `Onyx` | `Jugador1234` |

## Ejecución

```powershell
uvicorn main:app --reload
```

Un solo servidor publica todo:

| Ruta | Contenido |
|---|---|
| <http://127.0.0.1:8000/> | SPA |
| <http://127.0.0.1:8000/docs> | Swagger UI |
| <http://127.0.0.1:8000/redoc> | ReDoc |
| <http://127.0.0.1:8000/openapi.json> | Esquema OpenAPI |
| <http://127.0.0.1:8000/health> | Estado del servicio |

En Swagger, usá el botón **Authorize** con un usuario y contraseña. Swagger obtiene el token desde `POST /auth/login` y lo envía como `Authorization: Bearer <token>`.

## Pruebas

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

Cada prueba usa una base SQLite temporal, así que no modifica la base local.

## Variables de entorno

| Variable | Para qué sirve |
|---|---|
| `SECRET_KEY` | Firma y valida los tokens JWT. Usá una cadena larga y aleatoria en producción. |
| `DATABASE_URL` | URL de SQLAlchemy. Por defecto, `sqlite:///./arenagg.db`. |
| `TOKEN_EXPIRACION_MINUTOS` | Minutos de validez del token. Por defecto, `120`. |
| `CORS_ORIGINS` | Orígenes externos permitidos, separados por coma. La SPA servida por Uvicorn usa el mismo origen. |

## Autenticación

`POST /auth/login` recibe `application/x-www-form-urlencoded` con `username` y `password`. El usuario puede ser el nombre de usuario o el correo. La respuesta incluye `access_token`, `token_type`, `expires_in` y los datos del usuario.

Los endpoints protegidos esperan `Authorization: Bearer <token>`. El token incluye una huella del hash de la contraseña, por lo que cambiar la contraseña invalida los tokens emitidos antes del cambio.

## Flujo de un torneo

1. El admin crea el torneo con modalidad, formato, cupo, premio y reglas.
2. Los jugadores se inscriben, o el capitán inscribe al equipo con el roster completo.
3. El admin inicia el torneo y se genera la llave con los pases directos necesarios.
4. Cuando una partida tiene los dos participantes, los capitanes reciben el aviso y entran a la sala.
5. Un capitán carga el marcador. El rival lo confirma o lo disputa.
6. Si hay disputa, el admin carga el marcador final y el ganador avanza.
7. Al confirmar la final se actualizan el campeón y la tabla de posiciones.

Un resultado cargado por un administrador queda confirmado en el acto. El marcador es por mapas y respeta el formato: BO1 `1-0`; BO3 `2-0` o `2-1`; BO5 `3-0`, `3-1` o `3-2`.

## Notificaciones

Las notificaciones se guardan en la base. La SPA consulta `GET /notificaciones/resumen` cada 20 segundos para actualizar el contador y mostrar toasts. La bandeja completa se obtiene con `GET /notificaciones`. No se usan WebSockets ni Socket.IO.

## API

Todas las rutas devuelven JSON. Los errores de negocio tienen la forma `{"detail": "...", "errores": {...}}`.

### Autenticación

| Método | Ruta | Acceso |
|---|---|---|
| POST | `/auth/registro` | Público |
| POST | `/auth/login` | Público |
| GET | `/auth/me` | Token |

### Usuarios

| Método | Ruta | Acceso |
|---|---|---|
| GET | `/usuarios` | Admin |
| GET | `/usuarios/me` | Token |
| GET / PUT / DELETE | `/usuarios/{usuario_id}` | Propio usuario o admin; la baja es solo para admin |
| GET | `/usuarios/{usuario_id}/historial` | Público |
| GET | `/estadisticas` | Público |

### Torneos, inscripciones y partidas

| Método | Ruta | Acceso |
|---|---|---|
| GET / POST | `/torneos` | Público / Admin |
| GET / PUT / DELETE | `/torneos/{torneo_id}` | Público / Admin |
| GET | `/videojuegos` | Público |
| GET | `/torneos/{torneo_id}/participantes` | Público |
| POST / DELETE | `/torneos/{torneo_id}/inscribirse` | Token |
| GET | `/inscripciones` | Admin |
| DELETE | `/inscripciones/{inscripcion_id}` | Admin |
| POST | `/torneos/{torneo_id}/iniciar` | Admin |
| POST | `/torneos/{torneo_id}/reiniciar` | Admin |
| GET | `/torneos/{torneo_id}/partidas` | Público |
| GET | `/torneos/{torneo_id}/partidas/{partida_id}` | Público |
| GET | `/torneos/{torneo_id}/mi-partida` | Token |
| GET | `/torneos/{torneo_id}/equipos-disponibles` | Token |
| GET | `/torneos/{torneo_id}/posiciones` | Público |
| GET | `/partidas/{partida_id}` | Público |
| POST | `/torneos/{torneo_id}/partidas/{partida_id}/programar` | Admin |
| POST | `/torneos/{torneo_id}/partidas/{partida_id}/resultado` | Admin o capitán |
| POST | `/torneos/{torneo_id}/partidas/{partida_id}/confirmar` | Capitán rival |
| POST | `/torneos/{torneo_id}/partidas/{partida_id}/disputar` | Capitán rival |
| POST | `/torneos/{torneo_id}/partidas/{partida_id}/resolver` | Admin |
| POST | `/torneos/{torneo_id}/partidas/{partida_id}/rechazar` | Admin |

### Equipos

| Método | Ruta | Acceso |
|---|---|---|
| GET / POST | `/equipos` | Público / Token |
| GET | `/equipos/mios` | Token |
| GET | `/equipos/invitaciones` | Token |
| GET / PUT / DELETE | `/equipos/{equipo_id}` | Público / Capitán o admin |
| POST | `/equipos/{equipo_id}/invitar` | Capitán |
| POST | `/equipos/{equipo_id}/invitaciones/{membresia_id}/aceptar` | Invitado |
| POST | `/equipos/{equipo_id}/invitaciones/{membresia_id}/rechazar` | Invitado |
| DELETE | `/equipos/{equipo_id}/miembros/{membresia_id}` | Capitán |
| POST | `/equipos/{equipo_id}/salir` | Integrante |
| POST | `/equipos/{equipo_id}/capitan/{usuario_id}` | Capitán |
| GET | `/equipos/{equipo_id}/torneos-disponibles` | Token |

### Notificaciones

| Método | Ruta | Acceso |
|---|---|---|
| GET | `/notificaciones` | Token |
| GET | `/notificaciones/resumen` | Token |
| POST | `/notificaciones/{notificacion_id}/leer` | Dueño |
| POST | `/notificaciones/leer-todas` | Token |

## Estructura

```
torneos_gamer/
├── main.py                 # Punto de entrada para Uvicorn
├── app_factory.py          # Fábrica de la app, CORS, errores y SPA
├── config.py               # Configuración con pydantic-settings
├── database/
│   ├── base.py             # Base declarativa y utilidades de fechas
│   └── session.py          # Engine, sesiones y dependencia get_db
├── models/                 # Modelos SQLAlchemy 2
├── schemas/                # Schemas Pydantic de entrada y salida
├── services/               # Reglas de usuarios, torneos, equipos y avisos
├── security/               # JWT, hash de contraseñas y dependencias
├── controllers/            # Routers de FastAPI
├── frontend/
│   ├── index.html
│   └── assets/
│       ├── css/estilos.css
│       ├── audio/faceit-ready.mp3
│       └── js/             # SPA modular con rutas hash
├── tests/                  # Pruebas de la API y del seed
├── seed_demo.py            # Datos de demostración
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

El frontend usa módulos ES nativos, Bootstrap por CDN y rutas `#/...`. No requiere compilación ni un servidor aparte.
