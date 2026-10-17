from app.cli import cargar_datos_demo


def test_openapi_publicado(client):
    especificacion = client.get("/api/v1/openapi.json").json
    assert especificacion["info"]["title"] == (
        "RescueSync - Sistema Nacional de Gestión de Recursos y Riesgos"
    )
    assert "/api/v1/recursos/disponibilidad" in especificacion["paths"]


def test_error_uniforme(client):
    respuesta = client.get("/api/v1/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.json == {
        "codigo": "NO_ENCONTRADO",
        "mensaje": "El recurso no existe.",
        "detalles": {},
    }


def test_seed_es_idempotente():
    cargar_datos_demo()
    cargar_datos_demo()
