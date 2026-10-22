import json

import pytest

from app.security import RolSistema
from tests.utiles import headers


def test_lista_solo_habilitadas(client):
    respuesta = client.get("/api/v1/ongs?habilitada=true", headers=headers())
    assert respuesta.status_code == 200
    assert len(respuesta.json) == 2
    assert all(ong["habilitada"] for ong in respuesta.json)


def test_lista_no_habilitadas(client):
    respuesta = client.get("/api/v1/ongs?habilitada=false", headers=headers())
    assert respuesta.status_code == 200
    assert len(respuesta.json) == 1
    assert respuesta.json[0]["estado"] == "PENDIENTE"


def test_detalle_inexistente(client):
    respuesta = client.get("/api/v1/ongs/999999", headers=headers())
    assert respuesta.status_code == 404
    assert respuesta.json["codigo"] == "NO_ENCONTRADO"


def test_parametro_mal_escrito_no_devuelve_todo(client):
    respuesta = client.get("/api/v1/ongs?habilitadas=true", headers=headers())
    assert respuesta.status_code == 422
    assert "habilitadas" in respuesta.json["detalles"]["query"]


def test_valor_invalido_de_habilitada(client):
    respuesta = client.get("/api/v1/ongs?habilitada=talvez", headers=headers())
    assert respuesta.status_code == 422
    assert respuesta.json["codigo"] == "VALIDACION"


def test_paginacion_sigue_aceptando_page_y_page_size(client):
    respuesta = client.get("/api/v1/ongs?habilitada=true&page=2&page_size=1", headers=headers())
    assert respuesta.status_code == 200
    assert len(respuesta.json) == 1
    assert json.loads(respuesta.headers["X-Pagination"])["total"] == 2


@pytest.mark.parametrize(
    "ruta",
    [
        "/api/v1/ongs",
        "/api/v1/ongs/1",
        "/api/v1/ongs/1/certificaciones",
    ],
)
def test_consultas_de_ongs_exigen_token(client, ruta):
    respuesta = client.get(ruta)
    assert respuesta.status_code == 401
    assert respuesta.json["codigo"] == "NO_AUTENTICADO"


def test_consultas_de_ongs_no_son_para_el_rol_ong(client):
    respuesta = client.get("/api/v1/ongs", headers=headers(RolSistema.ONG))
    assert respuesta.status_code == 403
    assert respuesta.json["codigo"] == "PROHIBIDO"


@pytest.mark.parametrize("rol", [RolSistema.WEBAPP, RolSistema.BONITA, RolSistema.AUDITOR])
def test_consultas_de_ongs_para_cuentas_de_servicio(client, rol):
    assert client.get("/api/v1/ongs", headers=headers(rol)).status_code == 200
