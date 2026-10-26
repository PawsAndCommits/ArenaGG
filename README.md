# ArenaGG

Aplicación web para organizar torneos de videojuegos. Está hecha con Flask y SQLite, y la interfaz usa Bootstrap 5.

Qué se puede hacer:

- Registrarse e iniciar sesión con usuario y contraseña, o con Steam.
- Crear torneos individuales o por equipos, con fecha, cupo y estado.
- Inscribirse a un torneo y controlar los lugares disponibles.
- Armar las llaves de eliminación directa al iniciar el torneo.
- Cargar resultados: el ganador pasa solo a la ronda siguiente.
- Ver la tabla de posiciones y el historial de cada jugador.
- Avisar en tiempo real cuando hay una partida lista para jugar.
- Asignar un servidor de CS2 a una partida, prepararlo por RCON y recibir el resultado por webhook.

## Requisitos

- Python 3.10 o superior
- pip

Las dependencias están en `requirements.txt`.

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Después completá `.env` con tus claves. La base `instance/torneos.db` se crea sola la primera vez que arranca la app.

Para crear el primer administrador:

```powershell
flask --app app crear-admin
```

Si querés arrancar con datos de prueba:

```powershell
python seed_demo.py
```

Eso crea el usuario `admin` con la clave `Admin1234` y seis jugadores (`ShadowFox`, `NeoBlaze`, `PixelQueen`, `Ragnar`, `LunaByte`, `Kairo`) con la clave `Jugador1234`.

## Ejecución

```powershell
python app.py
```

La app queda en <http://127.0.0.1:5000>. Conviene usar `python app.py` en vez de `flask run`, porque el servidor necesita Socket.IO.

## Variables de entorno

| Variable | Para qué sirve |
|---|---|
| `STEAM_API_KEY` | Leer el perfil y las estadísticas de CS2. Se obtiene en <https://steamcommunity.com/dev/apikey>. |
| `CS2_WEBHOOK_SECRET` | Clave para firmar los resultados que manda el servidor de CS2. |
| `SECRET_KEY` | Opcional. Si no está, la app genera una en `instance/secret_key.txt`. |

El archivo `.env` está en `.gitignore`, así que las claves no se suben al repositorio.

Para ver las estadísticas de CS2, el usuario tiene que tener el perfil y los detalles de juego públicos en Steam.

## Servidores de CS2

Para registrar un servidor:

```powershell
flask --app app crear-servidor
```

Pide nombre, IP, puerto RCON y contraseña. Después, desde el detalle de una partida, el admin puede elegir el servidor y la app le manda los comandos por RCON para dejarla preparada.

### Webhook de resultados

El plugin del servidor tiene que mandar un POST con el cuerpo firmado:

```http
POST /api/cs2/webhook/match-result
X-CS2-Signature: <hmac-sha256 en hex del cuerpo>
Content-Type: application/json

{"partida_id": 12, "puntaje1": 13, "puntaje2": 9}
```

La firma se calcula así:

```python
import hashlib
import hmac
import json

cuerpo = json.dumps({"partida_id": 12, "puntaje1": 13, "puntaje2": 9}).encode()
firma = hmac.new(CLAVE.encode(), cuerpo, hashlib.sha256).hexdigest()
```

Si la firma no coincide, la ruta responde 401.

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
├── app.py                 # Arranque de Flask, configuración, errores y comandos
├── extensiones.py         # Instancia de Socket.IO
├── models.py              # Tablas de la base
├── services.py            # Reglas de negocio
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
│   └── cs2_webhook.py
├── templates/
├── static/
│   ├── css/estilos.css
│   ├── js/main.js
│   └── audio/faceit-ready.mp3
├── postman/
├── requirements.txt
└── instance/torneos.db    # Se crea al arrancar
```

El sonido de aviso de partida está en `static/audio/faceit-ready.mp3`.
