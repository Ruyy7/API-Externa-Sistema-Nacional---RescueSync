"""Los endpoints de I-3.4 exigen el token de una cuenta de servicio con el rol adecuado."""

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


def test_bonita_no_puede_reservar(client):
    respuesta = client.post(URL, json=pedido(), headers=headers(RolSistema.BONITA))
    assert respuesta.status_code == 403
    assert respuesta.json["codigo"] == "PROHIBIDO"


def test_la_webapp_y_bonita_pueden_confirmar_pero_el_auditor_no(client):
    compromiso = reserva_creada(client)
    cuerpo = {"items": [{"tipo_recurso": "PARAMEDICO", "cantidad": 5}]}
    url = f"{URL}/{compromiso['id']}/confirmacion"
    assert client.post(url, json=cuerpo, headers=headers(RolSistema.AUDITOR)).status_code == 403
    assert client.post(url, json=cuerpo, headers=headers(RolSistema.WEBAPP)).status_code == 200
    # Bonita reintenta la misma adjudicación: idempotente
    assert client.post(url, json=cuerpo, headers=headers(RolSistema.BONITA)).status_code == 200


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
