# ArenaGG

Plataforma de torneos de videojuegos con equipos, llaves de eliminación directa y resultados confirmados por los capitanes. Flask, SQLite, Bootstrap y Socket.IO.

## Qué incluye

- Cuentas con usuario y contraseña, o inicio de sesión con Steam.
- Torneos individuales y por equipos, con formato BO1, BO3 o BO5.
- Equipos con escudo, tag, roster, invitaciones y capitanía transferible.
- Inscripción individual o del equipo completo, con control de cupos y roster.
- Llaves de eliminación directa con pases directos para cupos que no son potencia de dos.
- Sala de partida con el marcador, los rosters y el estado del resultado.
- El capitán carga el marcador, el rival lo confirma y el admin resuelve disputas.
- Tabla de posiciones con victorias, diferencia de mapas, winrate y racha.
- Notificaciones persistentes con campanita, contador, toasts y aviso de partida lista.
- Historial de torneos por jugador y perfil público.
- Modo servidores opcional para CS2: RCON y webhook de resultados.

## Requisitos

- Python 3.10 o superior
- pip

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Completá `.env` con tus claves. La base `instance/torneos.db` se crea sola la primera vez que arranca la app y las columnas nuevas se agregan con la migración automática.

Para crear el primer administrador:

```powershell
flask --app app crear-admin
```

Para cargar datos de prueba:

```powershell
python seed_demo.py
```

Crea `admin / Admin1234`, diez jugadores con clave `Jugador1234`, dos equipos de Valorant (Night Owls y Red Dragons) y cuatro torneos.

## Ejecución

```powershell
python app.py
```

La app queda en <http://127.0.0.1:5000>. Usá `python app.py` y no `flask run`: Socket.IO necesita su propio servidor.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

Las pruebas usan una base SQLite temporal y no tocan `instance/torneos.db`.

## Variables de entorno

| Variable | Para qué sirve |
|---|---|
| `STEAM_API_KEY` | Leer el perfil y las estadísticas de CS2. Se obtiene en <https://steamcommunity.com/dev/apikey>. |
| `MODO_SERVIDORES` | `false` por defecto. Si está en `true`, habilita RCON y el webhook de CS2. |
| `CS2_WEBHOOK_SECRET` | Clave para firmar los resultados que manda el servidor de CS2. |
| `SECRET_KEY` | Opcional. Si no está, la app genera una en `instance/secret_key.txt`. |
| `SOCKETIO_ORIGINS` | Opcional. Orígenes permitidos para Socket.IO, separados por coma. |

El archivo `.env` está en `.gitignore`, así que las claves no se suben al repositorio.

## Flujo de un torneo

1. El admin crea el torneo con modalidad, formato, cupo, premio y reglas.
2. Los jugadores se inscriben, o el capitán inscribe al equipo con el roster completo.
3. El admin inicia el torneo y se genera la llave con los pases directos necesarios.
4. Cuando una partida tiene los dos participantes, los capitanes reciben el aviso y entran a la sala.
5. Un capitán carga el marcador. El rival lo confirma o lo disputa.
6. Si hay disputa, el admin carga el marcador final. El ganador avanza solo.
7. El campeón y la tabla de posiciones se actualizan al confirmar la final.

Un resultado cargado por un administrador queda confirmado en el acto. Los resultados cargados por un capitán quedan pendientes hasta que los confirme el capitán rival.

## Servidores de CS2

Esta parte está apagada por defecto. Para usarla, poné `MODO_SERVIDORES=true` en `.env` (y un `CS2_WEBHOOK_SECRET` si vas a recibir resultados del servidor) y registrá un servidor:

```powershell
flask --app app crear-servidor
```

Pide nombre, IP, puerto RCON y contraseña. Después, desde la sala de una partida, el admin puede asignar el servidor y la app manda los comandos por RCON.

Con el modo apagado, las rutas de servidores y el webhook responden 404, y la sala no muestra la sección de servidor.

### Webhook de resultados

El plugin del servidor manda un POST con el cuerpo firmado:

```http
POST /api/cs2/webhook/match-result
X-CS2-Signature: <hmac-sha256 en hex del cuerpo>
Content-Type: application/json

{"partida_id": 12, "puntaje1": 2, "puntaje2": 1}
```

El marcador es por mapas y respeta el formato del torneo: BO1 1-0, BO3 2-0 o 2-1, BO5 3-0, 3-1 o 3-2.

La firma se calcula así:

```python
import hashlib
import hmac
import json

cuerpo = json.dumps({"partida_id": 12, "puntaje1": 2, "puntaje2": 1}).encode()
firma = hmac.new(CLAVE.encode(), cuerpo, hashlib.sha256).hexdigest()
```

Si la firma no coincide, la ruta responde 401. Si el secreto no está configurado, responde 503.

## API

Las rutas privadas usan `Authorization: Bearer <token>`. El token se obtiene en `POST /api/auth/login`.

| Método | Ruta | Acceso |
|---|---|---|
| POST | `/api/auth/registro` | Público |
| POST | `/api/auth/login` | Público |
| GET | `/api/auth/me` | Token |
| GET | `/api/usuarios` | Admin |
| GET / PUT | `/api/usuarios/<id>` | Token |
| DELETE | `/api/usuarios/<id>` | Admin |
| GET | `/api/usuarios/<id>/historial` | Público |
| GET | `/api/torneos` | Público |
| GET | `/api/torneos/<id>` | Público |
| POST | `/api/torneos` | Admin |
| PUT / DELETE | `/api/torneos/<id>` | Admin |
| POST / DELETE | `/api/torneos/<id>/inscribirse` | Token |
| GET | `/api/torneos/<id>/participantes` | Público |
| GET | `/api/inscripciones` | Admin |
| DELETE | `/api/inscripciones/<id>` | Admin |
| POST | `/api/torneos/<id>/iniciar` | Admin |
| POST | `/api/torneos/<id>/partidas/<partida_id>/resultado` | Token (admin o capitán) |
| POST | `/api/cs2/webhook/match-result` | Firma HMAC |

Hay una colección de Postman en `postman/Torneos.postman_collection.json`. Para usarla, completá `adminUser` y `adminPassword` en las variables y ejecutá las carpetas en orden.

## Estructura

```
torneos_gamer/
├── app.py                 # Arranque, configuración, errores y comandos
├── extensiones.py         # Instancia de Socket.IO
├── models.py              # Tablas de la base
├── services.py            # Reglas de torneos, llaves, resultados y tabla
├── equipos.py             # Altas, roster e invitaciones
├── notificaciones.py      # Persistencia y envío de avisos
├── migraciones.py         # Columnas e índices para bases existentes
├── seguridad.py           # Login, roles, CSRF y tokens de la API
├── seed_demo.py           # Datos de prueba
├── integraciones/
│   ├── steam.py           # OpenID y Web API de Steam
│   ├── rcon.py            # Cliente RCON
│   └── cs2.py             # Preparación de partidas en el servidor
├── routes/
│   ├── main.py
│   ├── usuarios.py
│   ├── torneos.py
│   ├── equipos.py
│   ├── notificaciones.py
│   └── cs2_webhook.py
├── templates/
├── static/
│   ├── css/estilos.css
│   ├── js/main.js
│   └── audio/faceit-ready.mp3
├── tests/
├── postman/
├── requirements.txt
└── instance/torneos.db    # Se crea al arrancar
```

El sonido de aviso de partida está en `static/audio/faceit-ready.mp3`.
