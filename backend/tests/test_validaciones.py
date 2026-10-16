"""I-3.3: validación por niveles de competencia.

Datos del seed que usan estos tests (disponible = total - bloqueada - comprometida):
- 30-11111111-1 (HABILITADA): PARAMEDICO 12-2-0 = 10, RESCATISTA 20-3-2 = 15; sin BOMBERO.
- 30-33333333-3 (PENDIENTE): PARAMEDICO 100.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy import select

from app.extensions import db
from app.models import (
    ONG,
    Compromiso,
    CompromisoItem,
    Convocatoria,
    InventarioRecurso,
    MotivoNivel,
    NivelCompetencia,
    RolSugerido,
    TipoRecurso,
)
from app.services.validaciones import evaluar_linea

RIO, PENDIENTE = "30-11111111-1", "30-33333333-3"
URL = "/api/v1/validaciones"


@pytest.mark.parametrize(
    ("ofrecida", "requerida", "habilitada", "impedimento", "esperado"),
    [
        ("5", "5", "10", None, ("5", "TOTAL", None, "PRINCIPAL")),
        ("3", "5", "10", None, ("3", "TOTAL", None, "APOYO")),
        ("14", "5", "10", None, ("10", "PARCIAL", "EXCEDE_DISPONIBLE", "PRINCIPAL")),
        ("14", "20", "10", None, ("10", "PARCIAL", "EXCEDE_DISPONIBLE", "APOYO")),
        ("5", "5", "0", None, ("0", "NO_HABILITADO", "SIN_DISPONIBILIDAD", None)),
        ("5", "5", "10", MotivoNivel.NO_INSCRIPTA, ("0", "NO_HABILITADO", "NO_INSCRIPTA", None)),
    ],
)
def test_evaluar_linea(ofrecida, requerida, habilitada, impedimento, esperado):
    resultado = evaluar_linea(
        Decimal(ofrecida), Decimal(requerida), Decimal(habilitada), impedimento
    )
    aceptada, nivel, motivo, rol = esperado
    assert resultado.cantidad_aceptada == Decimal(aceptada)
    assert resultado.nivel == NivelCompetencia(nivel)
    assert resultado.motivo == (MotivoNivel(motivo) if motivo else None)
    assert resultado.rol_sugerido == (RolSugerido(rol) if rol else None)


@pytest.fixture
def auth(app):
    with app.app_context():
        return {"Authorization": f"Bearer {create_access_token(identity='bonita')}"}


def _item(cuit, tipo, ofrecida, requerida="5", lote="LOTE-1"):
    return {
        "lote_referencia": lote,
        "ong_cuit": cuit,
        "tipo_recurso": tipo,
        "cantidad_ofrecida": ofrecida,
        "cantidad_requerida": requerida,
    }


def _pedido(*ofertas):
    return {
        "convocatoria_referencia": "CONV-1",
        "ofertas": [
            {"oferta_referencia": f"OF-{n}", "items": items} for n, items in enumerate(ofertas, 1)
        ],
    }


def _validar(client, auth, pedido):
    respuesta = client.post(URL, json=pedido, headers=auth)
    assert respuesta.status_code == 200, respuesta.json
    return respuesta.json["ofertas"]


def test_requiere_jwt(client):
    assert client.post(URL, json=_pedido([_item(RIO, "PARAMEDICO", "1")])).status_code == 401


def test_acepta_parcialmente_sin_rechazar_la_oferta(client, auth):
    """Las líneas se evalúan una por una; la oferta conserva lo que sí califica."""
    [oferta] = _validar(
        client,
        auth,
        _pedido(
            [
                _item(RIO, "PARAMEDICO", "14"),
                # Misma ONG y categoría en dos lotes: comparten los 15 disponibles.
                _item(RIO, "RESCATISTA", "10", lote="LOTE-2"),
                _item(RIO, "RESCATISTA", "10", requerida="10", lote="LOTE-3"),
                _item(RIO, "BOMBERO", "2"),
            ]
        ),
    )
    paramedicos, rescatistas_1, rescatistas_2, bomberos = oferta["items"]
    assert oferta["nivel"] == "PARCIAL"
    assert paramedicos["cantidad_habilitada"] == "10.00"
    assert paramedicos["cantidad_aceptada"] == "10.00"
    assert (paramedicos["nivel"], paramedicos["rol_sugerido"]) == ("PARCIAL", "PRINCIPAL")
    assert (rescatistas_1["cantidad_aceptada"], rescatistas_1["nivel"]) == ("10.00", "TOTAL")
    assert rescatistas_2["cantidad_habilitada"] == "5.00"
    assert (rescatistas_2["nivel"], rescatistas_2["rol_sugerido"]) == ("PARCIAL", "APOYO")
    assert (bomberos["nivel"], bomberos["motivo"]) == ("NO_HABILITADO", "NO_INSCRIPTA")
    assert bomberos["rol_sugerido"] is None


def test_ong_no_habilitada_o_desconocida_no_aporta(client, auth):
    [oferta] = _validar(
        client,
        auth,
        _pedido([_item(PENDIENTE, "PARAMEDICO", "5"), _item("30-99999999-9", "PARAMEDICO", "5")]),
    )
    assert oferta["nivel"] == "NO_HABILITADO"
    assert [i["motivo"] for i in oferta["items"]] == ["ONG_NO_HABILITADA", "ONG_NO_REGISTRADA"]
    assert all(i["cantidad_aceptada"] == "0.00" for i in oferta["items"])


def test_ofertas_distintas_no_se_descuentan_entre_si(client, auth):
    """Son alternativas para el municipio; la sobre-asignación la frena I-3.4 al adjudicar."""
    ofertas = _validar(
        client,
        auth,
        _pedido([_item(RIO, "PARAMEDICO", "10")], [_item(RIO, "PARAMEDICO", "10")]),
    )
    assert [o["nivel"] for o in ofertas] == ["TOTAL", "TOTAL"]


def test_la_reserva_propia_no_cuenta_en_contra(client, auth):
    """Los 2 paramédicos bloqueados del seed pasan a ser una reserva de OF-1."""
    ong = db.session.scalar(select(ONG).filter_by(cuit=RIO))
    inventario = db.session.scalar(
        select(InventarioRecurso)
        .join(InventarioRecurso.tipo_recurso)
        .where(InventarioRecurso.ong_id == ong.id, TipoRecurso.codigo == "PARAMEDICO")
    )
    convocatoria = Convocatoria(
        referencia="CONV-1",
        emergencia_referencia="EMG-1",
        fecha_cierre=datetime(2026, 10, 20, tzinfo=UTC),
        fecha_limite_adjudicacion=datetime(2026, 10, 25, tzinfo=UTC),
    )
    compromiso = Compromiso(
        convocatoria=convocatoria, ong=ong, oferta_referencia="OF-1", creado_por="tests"
    )
    compromiso.items.append(
        CompromisoItem(
            ong_id=ong.id, inventario_recurso=inventario, cantidad_reservada=Decimal("2")
        )
    )
    db.session.add(compromiso)
    db.session.commit()

    propia, ajena = _validar(
        client,
        auth,
        _pedido([_item(RIO, "PARAMEDICO", "12")], [_item(RIO, "PARAMEDICO", "12")]),
    )
    assert propia["items"][0]["cantidad_aceptada"] == "12.00"
    assert ajena["items"][0]["cantidad_aceptada"] == "10.00"


def test_tipo_de_recurso_desconocido_es_422(client, auth):
    respuesta = client.post(URL, json=_pedido([_item(RIO, "DRON", "1")]), headers=auth)
    assert respuesta.status_code == 422
    assert respuesta.json["codigo"] == "TIPO_RECURSO_DESCONOCIDO"
    assert respuesta.json["detalles"] == {"tipos_recurso": ["DRON"]}


def test_cantidad_no_positiva_es_422(client, auth):
    respuesta = client.post(URL, json=_pedido([_item(RIO, "PARAMEDICO", "0")]), headers=auth)
    assert respuesta.status_code == 422
    assert respuesta.json["codigo"] == "VALIDACION"


def test_documentado_en_swagger_con_jwt(client):
    especificacion = client.get("/api/v1/openapi.json").json
    assert especificacion["paths"]["/api/v1/validaciones"]["post"]["security"] == [
        {"bearerAuth": []}
    ]
