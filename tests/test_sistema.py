"""Pruebas del servicio: SPA, Swagger, OpenAPI y CORS."""
from tests.ayudas import auth


def test_health(client):
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"
    assert respuesta.json()["app"] == "ArenaGG"


def test_spa_y_assets(client):
    raiz = client.get("/")
    assert raiz.status_code == 200
    assert "text/html" in raiz.headers["content-type"]
    assert 'src="/assets/js/app.js"' in raiz.text
    assert "ArenaGG" in raiz.text

    indice = client.get("/index.html")
    assert indice.status_code == 200
    assert indice.text == raiz.text

    inicio = client.get("/assets/js/pages/inicio.js")
    assert inicio.status_code == 200
    assert "Ganá en arena." in inicio.text

    estilos = client.get("/assets/css/estilos.css")
    assert estilos.status_code == 200
    assert "--rojo" in estilos.text
    assert "hero-titulo" in estilos.text


def test_swagger_y_esquema_openapi(client):
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "swagger" in docs.text.lower()

    esquema = client.get("/openapi.json").json()
    assert esquema["info"]["title"] == "ArenaGG"
    assert "/auth/login" in esquema["paths"]
    assert "/usuarios/me" in esquema["paths"]
    assert all(not ruta.startswith("/api/") for ruta in esquema["paths"])

    seguridades = esquema["components"]["securitySchemes"].values()
    assert any(
        seguridad.get("type") == "oauth2"
        and seguridad["flows"]["password"]["tokenUrl"] == "/auth/login"
        for seguridad in seguridades
    )

    protegida = esquema["paths"]["/usuarios/me"]["get"]
    assert protegida["security"]

    login = esquema["paths"]["/auth/login"]["post"]
    assert "application/x-www-form-urlencoded" in login["requestBody"]["content"]


def test_cors_permite_origen_configurado(client):
    origen = "http://localhost:5173"
    respuesta = client.options(
        "/torneos",
        headers={
            "Origin": origen,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == origen
    assert "GET" in respuesta.headers["access-control-allow-methods"]

    consulta = client.get("/torneos", headers={"Origin": origen})
    assert consulta.headers["access-control-allow-origin"] == origen


def test_cors_rechaza_origen_desconocido(client):
    respuesta = client.get("/torneos", headers={"Origin": "https://sitio.example"})
    assert "access-control-allow-origin" not in respuesta.headers


def test_rutas_inexistentes_responden_404(client):
    assert client.get("/no-existe").status_code == 404
    assert client.get("/api/torneos").status_code == 404


def test_token_bearer_obtenido_por_login(client, jugador):
    respuesta = client.get("/usuarios/me", headers=jugador["headers"])
    assert respuesta.status_code == 200
    assert respuesta.json()["username"] == "jugador"
    assert auth(client.post(
        "/auth/login",
        data={"username": "jugador", "password": "Jugador1234"},
    ).json()["access_token"])["Authorization"].startswith("Bearer ")
