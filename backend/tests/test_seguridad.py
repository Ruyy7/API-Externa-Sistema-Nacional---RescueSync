"""Los endpoints de I-3.4 exigen el token de una cuenta de servicio con el rol adecuado."""

import pytest

from app.security import RolSistema
from tests.utiles import URL, headers, pedido, reserva_creada


def test_sin_token_responde_401_uniforme(client):
    respuesta = client.post(URL, json=pedido())
    assert respuesta.status_code == 401
    assert respuesta.json["codigo"] == "NO_AUTENTICADO"
    assert respuesta.json["detalles"] == {}


def test_token_invalido_responde_401(client):
    respuesta = client.post(URL, json=pedido(), headers={"Authorization": "Bearer no-es-un-token"})
    assert respuesta.status_code == 401
    assert respuesta.json["codigo"] == "NO_AUTENTICADO"


def test_la_webapp_no_puede_reservar(client):
    respuesta = client.post(URL, json=pedido(), headers=headers(RolSistema.WEBAPP))
    assert respuesta.status_code == 403
    assert respuesta.json["codigo"] == "PROHIBIDO"


def test_solo_bonita_confirma(client):
    compromiso = reserva_creada(client)
    cuerpo = {"items": [{"tipo_recurso": "PARAMEDICO", "cantidad": 5}]}
    url = f"{URL}/{compromiso['id']}/confirmacion"
    assert client.post(url, json=cuerpo, headers=headers(RolSistema.AUDITOR)).status_code == 403
    assert client.post(url, json=cuerpo, headers=headers(RolSistema.WEBAPP)).status_code == 403
    assert client.post(url, json=cuerpo, headers=headers(RolSistema.BONITA)).status_code == 200
    # Bonita reintenta la misma adjudicación: idempotente
    assert client.post(url, json=cuerpo, headers=headers(RolSistema.BONITA)).status_code == 200


# --- Principio de orquestación (pauta de la cátedra del 19/11) ---------------------------------
# La webapp no invoca ninguna operación del proceso: validar, bloquear, comprometer, liberar ni
# cerrar. Las invoca solo Bonita. La cuenta de la webapp conserva las consultas.

OPERACIONES_DEL_PROCESO = [
    ("post", "/api/v1/validaciones"),
    ("post", "/api/v1/compromisos/verificacion"),
    ("post", "/api/v1/compromisos"),
    ("put", "/api/v1/compromisos/1"),
    ("post", "/api/v1/compromisos/1/cancelacion"),
    ("post", "/api/v1/compromisos/1/confirmacion"),
    ("put", "/api/v1/convocatorias/convocatoria-1"),
    ("post", "/api/v1/convocatorias/convocatoria-1/reformulacion"),
    ("post", "/api/v1/actividades"),
    ("post", "/api/v1/emergencias/emergencia-1/bloqueo"),
    ("post", "/api/v1/emergencias/emergencia-1/desbloqueo"),
    ("post", "/api/v1/emergencias/emergencia-1/adjudicacion"),
    ("post", "/api/v1/emergencias/emergencia-1/actividades"),
    ("post", "/api/v1/emergencias/emergencia-1/liberacion"),
    ("post", "/api/v1/emergencias/emergencia-1/cierre"),
]


@pytest.mark.parametrize(("metodo", "url"), OPERACIONES_DEL_PROCESO)
def test_la_webapp_no_puede_invocar_operaciones_del_proceso(client, metodo, url):
    respuesta = getattr(client, metodo)(url, json={}, headers=headers(RolSistema.WEBAPP))
    assert (respuesta.status_code, respuesta.json["codigo"]) == (403, "PROHIBIDO")


# Escrituras que no son operaciones del proceso: las públicas (login y registro de ONGs), las de la
# propia ONG y el ABM de inventario de una ONG por CUIT, que la webapp usa fuera del proceso.
FUERA_DEL_PROCESO = {
    ("POST", "/api/v1/login"),
    ("POST", "/api/v1/ongs"),
    ("PUT", "/api/v1/ongs/yo/categorias"),
    ("PUT", "/api/v1/ongs/cuit/<string:cuit>/categorias"),
}


def test_la_lista_cubre_todas_las_escrituras(app):
    """Toda escritura de la API es una operación del proceso (y está en la lista de arriba) o
    está fuera del proceso. Si se agrega un endpoint que escribe, este test obliga a decidirlo."""
    adaptador = app.url_map.bind("localhost")
    cubiertas = {
        (metodo.upper(), adaptador.match(url, method=metodo.upper(), return_rule=True)[0].rule)
        for metodo, url in OPERACIONES_DEL_PROCESO
    }
    escrituras = {
        (metodo, regla.rule)
        for regla in app.url_map.iter_rules()
        for metodo in regla.methods & {"POST", "PUT", "PATCH", "DELETE"}
    }
    sin_decidir = escrituras - FUERA_DEL_PROCESO - cubiertas
    assert not sin_decidir, sorted(sin_decidir)


def test_la_webapp_conserva_las_consultas(client):
    reserva_creada(client)
    webapp = headers(RolSistema.WEBAPP)
    assert client.get(URL, headers=webapp).status_code == 200
    assert client.get("/api/v1/actividades", headers=webapp).status_code == 200


def test_el_auditor_solo_consulta(client):
    compromiso = reserva_creada(client)
    auditor = headers(RolSistema.AUDITOR)
    assert client.get(f"{URL}/{compromiso['id']}", headers=auditor).status_code == 200
    assert client.post(f"{URL}/{compromiso['id']}/cancelacion", headers=auditor).status_code == 403


def test_swagger_documenta_el_token(client):
    especificacion = client.get("/api/v1/openapi.json").json
    assert "bearerAuth" in especificacion["components"]["securitySchemes"]
    reservar = especificacion["paths"]["/api/v1/compromisos"]["post"]
    assert reservar["security"] == [{"bearerAuth": []}]
    assert {"401", "403", "409", "422"} <= set(reservar["responses"])
