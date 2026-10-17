"""I-3.5: las actividades cumplidas liberan lo comprometido a medida que la ONG las informa.

Datos del seed que usan estos tests:
- Rescatistas del Río (30-11111111-1): PARAMEDICO 12 en total, 2 bloqueados, 0 comprometidos;
  RESCATISTA 20, 3 y 2. Los dos son reutilizables. No tiene RACION_ALIMENTO.
- Alimentos Solidarios (30-22222222-2): RACION_ALIMENTO 5000, 700 y 300. Es consumible.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import Actividad
from app.models.comun import ahora
from app.security import RolSistema
from tests.utiles import RIO, URL, confirmar, headers, inventario, reserva_creada

ACTIVIDADES = "/api/v1/actividades"
ALIMENTOS = "30-22222222-2"


def comprometido(
    client,
    *,
    items=(("PARAMEDICO", 5),),
    adjudicado=None,
    oferta: str = "oferta-1",
    emergencia: str = "emergencia-1",
    convocatoria: str = "conv-1",
    cuit: str = RIO,
) -> dict:
    """Reserva y adjudica: deja el compromiso COMPROMETIDO que el punto 4 le entrega al 5."""
    reserva = reserva_creada(
        client, oferta, items=items, emergencia=emergencia, convocatoria=convocatoria, cuit=cuit
    )
    respuesta = confirmar(client, reserva["id"], adjudicado or items)
    assert respuesta.status_code == 200, respuesta.json
    return respuesta.json


def actividad(
    referencia: str = "ACT-1",
    *,
    cantidad=3,
    tipo: str = "PARAMEDICO",
    emergencia: str = "emergencia-1",
    cuit: str = RIO,
    **extra,
) -> dict:
    return {
        "actividad_referencia": referencia,
        "emergencia_referencia": emergencia,
        "ong_cuit": cuit,
        "tipo_recurso": tipo,
        "cantidad": cantidad,
        "fecha": (ahora() - timedelta(hours=1)).isoformat(),
        "observaciones": "Tarea cumplida",
        **extra,
    }


def informar(client, cuerpo: dict, rol: RolSistema = RolSistema.WEBAPP):
    return client.post(ACTIVIDADES, json=cuerpo, headers=headers(rol))


def informada(client, cuerpo: dict) -> dict:
    respuesta = informar(client, cuerpo)
    assert respuesta.status_code == 201, respuesta.json
    return respuesta.json


def contadores(codigo: str, cuit: str = RIO) -> tuple:
    fila = inventario(codigo, cuit)
    return fila.cantidad_total, fila.cantidad_bloqueada, fila.cantidad_comprometida


def cantidad_de_actividades() -> int:
    return db.session.scalar(select(func.count()).select_from(Actividad))


# --- Seguridad -----------------------------------------------------------------------------


def test_requiere_token_de_servicio_con_rol_que_escribe(client):
    comprometido(client)
    assert client.post(ACTIVIDADES, json=actividad()).status_code == 401
    for rol in (RolSistema.AUDITOR, RolSistema.ONG):
        respuesta = informar(client, actividad(), rol)
        assert (respuesta.status_code, respuesta.json["codigo"]) == (403, "PROHIBIDO")
    assert informar(client, actividad(), RolSistema.BONITA).status_code == 201


def test_el_auditor_consulta(client):
    comprometido(client)
    registrada = informada(client, actividad())
    auditor = headers(RolSistema.AUDITOR)
    assert client.get(ACTIVIDADES, headers=auditor).status_code == 200
    assert client.get(f"{ACTIVIDADES}/{registrada['id']}", headers=auditor).status_code == 200


# --- Liberar a medida que se cumplen las actividades ---------------------------------------


def test_un_reutilizable_vuelve_al_stock(client):
    """3 de 5 paramédicos terminaron: vuelven a estar disponibles; el total no cambia."""
    compromiso = comprometido(client)
    assert contadores("PARAMEDICO") == (12, 2, 5)

    registrada = informada(client, actividad(cantidad=3))

    assert registrada["accion"] == "LIBERADO"
    assert registrada["origen"] == "INFORMADA"
    assert registrada["compromiso_id"] == compromiso["id"]
    assert registrada["estado_compromiso"] == "COMPROMETIDO"
    assert registrada["item"] == {
        "tipo_recurso": {"codigo": "PARAMEDICO", "nombre": "Paramédico"},
        "cantidad_comprometida": "5.00",
        "cantidad_liberada": "3.00",
        "cantidad_pendiente": "2.00",
    }
    assert registrada["registrada_por"] == "tests"
    assert contadores("PARAMEDICO") == (12, 2, 2)


def test_un_consumible_sale_del_stock(client):
    """500 raciones entregadas: bajan lo comprometido y el total; lo disponible no cambia."""
    comprometido(
        client,
        items=[("RACION_ALIMENTO", 1000)],
        adjudicado=[("RACION_ALIMENTO", 800)],
        cuit=ALIMENTOS,
    )
    assert contadores("RACION_ALIMENTO", ALIMENTOS) == (5000, 700, 1100)

    registrada = informada(client, actividad(cantidad=500, tipo="RACION_ALIMENTO", cuit=ALIMENTOS))

    assert registrada["accion"] == "CONSUMIDO"
    assert registrada["item"]["cantidad_pendiente"] == "300.00"
    assert contadores("RACION_ALIMENTO", ALIMENTOS) == (4500, 700, 600)
    assert inventario("RACION_ALIMENTO", ALIMENTOS).cantidad_disponible == 3200


def test_finaliza_el_compromiso_cuando_no_queda_nada_pendiente(client):
    compromiso = comprometido(client)
    informada(client, actividad("ACT-1", cantidad=3))
    ultima = informada(client, actividad("ACT-2", cantidad=2))

    assert ultima["estado_compromiso"] == "FINALIZADO"
    assert ultima["item"]["cantidad_pendiente"] == "0.00"
    detalle = client.get(f"{URL}/{compromiso['id']}", headers=headers()).json
    assert detalle["estado"] == "FINALIZADO"
    assert detalle["finalizado_en"] is not None
    assert detalle["items"][0]["cantidad_liberada"] == "5.00"
    assert contadores("PARAMEDICO") == (12, 2, 0)


def test_un_item_adjudicado_en_cero_no_impide_finalizar(client):
    """Adjudicación parcial: los rescatistas no se adjudicaron, así que no hay nada que liberar."""
    comprometido(
        client, items=[("PARAMEDICO", 5), ("RESCATISTA", 4)], adjudicado=[("PARAMEDICO", 5)]
    )
    registrada = informada(client, actividad(cantidad=5))
    assert registrada["estado_compromiso"] == "FINALIZADO"
    assert contadores("RESCATISTA") == (20, 3, 2)


# --- Reglas ----------------------------------------------------------------------------------


def test_no_se_libera_mas_de_lo_pendiente_y_nada_cambia(client):
    comprometido(client)
    informada(client, actividad("ACT-1", cantidad=3))

    respuesta = informar(client, actividad("ACT-2", cantidad=3))

    assert respuesta.status_code == 409, respuesta.json
    assert respuesta.json["codigo"] == "EXCEDE_PENDIENTE"
    assert respuesta.json["detalles"] == {
        "tipo_recurso": "PARAMEDICO",
        "pedida": "3.00",
        "pendiente": "2.00",
    }
    assert contadores("PARAMEDICO") == (12, 2, 2)
    assert cantidad_de_actividades() == 1


def test_repetir_el_pedido_es_un_reintento_y_no_libera_dos_veces(client):
    comprometido(client)
    cuerpo = actividad(cantidad=3)
    primera = informada(client, cuerpo)

    repetida = informar(client, cuerpo)

    assert repetida.status_code == 200, repetida.json
    assert repetida.json["id"] == primera["id"]
    assert contadores("PARAMEDICO") == (12, 2, 2)
    assert cantidad_de_actividades() == 1


def test_la_misma_referencia_con_otros_datos_es_un_conflicto(client):
    comprometido(client)
    informada(client, actividad("ACT-1", cantidad=3))
    respuesta = informar(client, actividad("ACT-1", cantidad=2))
    assert respuesta.status_code == 409
    assert respuesta.json["codigo"] == "ACTIVIDAD_DUPLICADA"
    assert contadores("PARAMEDICO") == (12, 2, 2)


def test_solo_se_libera_un_compromiso_comprometido(client):
    """Una reserva sin adjudicar no se libera; un compromiso finalizado tampoco."""
    reserva_creada(client, "oferta-1", items=[("PARAMEDICO", 5)])
    respuesta = informar(client, actividad())
    assert (respuesta.status_code, respuesta.json["codigo"]) == (409, "TRANSICION_INVALIDA")
    assert respuesta.json["detalles"]["compromisos"][0]["estado"] == "RESERVADO"
    assert contadores("PARAMEDICO") == (12, 7, 0)

    assert confirmar(client, 1, [("PARAMEDICO", 5)]).status_code == 200
    informada(client, actividad("ACT-1", cantidad=5))
    respuesta = informar(client, actividad("ACT-2", cantidad=1))
    assert (respuesta.status_code, respuesta.json["codigo"]) == (409, "TRANSICION_INVALIDA")
    assert respuesta.json["detalles"]["compromisos"][0]["estado"] == "FINALIZADO"


def test_sin_compromiso_para_esa_categoria_es_404(client):
    comprometido(client)
    respuesta = informar(client, actividad(tipo="RESCATISTA"))
    assert (respuesta.status_code, respuesta.json["codigo"]) == (404, "NO_ENCONTRADO")
    respuesta = informar(client, actividad(emergencia="otra-emergencia"))
    assert respuesta.status_code == 404
    respuesta = informar(client, actividad(cuit="30-99999999-9"))
    assert (respuesta.status_code, respuesta.json["codigo"]) == (422, "ONG_INEXISTENTE")


def test_con_dos_compromisos_en_la_emergencia_hay_que_indicar_la_oferta(client):
    """La ONG va sola en una oferta y en un consorcio en otra, las dos con paramédicos."""
    comprometido(client, items=[("PARAMEDICO", 3)], oferta="oferta-propia")
    consorcio = comprometido(client, items=[("PARAMEDICO", 3)], oferta="oferta-consorcio")

    respuesta = informar(client, actividad(cantidad=2))
    assert (respuesta.status_code, respuesta.json["codigo"]) == (422, "COMPROMISO_AMBIGUO")
    assert respuesta.json["detalles"] == {"ofertas": ["oferta-propia", "oferta-consorcio"]}

    registrada = informada(client, actividad(cantidad=2, oferta_referencia="oferta-consorcio"))
    assert registrada["compromiso_id"] == consorcio["id"]
    assert registrada["oferta_referencia"] == "oferta-consorcio"
    assert contadores("PARAMEDICO") == (12, 2, 4)


@pytest.mark.parametrize(
    ("cambios", "codigo"),
    [
        ({"cantidad": "2.5"}, "VALIDACION"),  # las personas se cuentan enteras
        ({"cantidad": 0}, "VALIDACION"),
        ({"fecha": (ahora() + timedelta(days=1)).isoformat()}, "FECHA_FUTURA"),
        ({"fecha": "no es una fecha"}, "VALIDACION"),
        ({"tipo_recurso": "DRON"}, "TIPO_RECURSO_DESCONOCIDO"),
        ({"actividad_referencia": "con espacios"}, "VALIDACION"),
        ({"observaciones": "x" * 2001}, "VALIDACION"),
    ],
)
def test_pedidos_invalidos_responden_422_sin_tocar_nada(client, cambios, codigo):
    comprometido(client)
    respuesta = informar(client, actividad(**cambios))
    assert respuesta.status_code == 422, respuesta.json
    assert respuesta.json["codigo"] == codigo
    assert contadores("PARAMEDICO") == (12, 2, 5)
    assert cantidad_de_actividades() == 0


def test_la_reserva_de_otras_ofertas_nunca_se_toca(client):
    """La liberación mueve lo comprometido; cantidad_bloqueada es del punto 4."""
    comprometido(client)
    reserva_creada(client, "oferta-2", items=[("PARAMEDICO", 4)], convocatoria="conv-2")
    assert contadores("PARAMEDICO") == (12, 6, 5)
    informada(client, actividad(cantidad=5))
    assert contadores("PARAMEDICO") == (12, 6, 0)


# --- Historial -------------------------------------------------------------------------------


def test_el_historial_suma_lo_liberado_y_se_filtra(client):
    compromiso = comprometido(client, items=[("PARAMEDICO", 5), ("RESCATISTA", 4)])
    informada(client, actividad("ACT-1", cantidad=3))
    informada(client, actividad("ACT-2", cantidad=2))
    informada(client, actividad("ACT-3", cantidad=4, tipo="RESCATISTA"))

    todas = client.get(f"{ACTIVIDADES}?emergencia=emergencia-1", headers=headers()).json
    assert [a["actividad_referencia"] for a in todas] == ["ACT-3", "ACT-2", "ACT-1"]
    paramedicos = client.get(f"{ACTIVIDADES}?tipo_recurso=PARAMEDICO", headers=headers()).json
    assert sum(Decimal(a["cantidad"]) for a in paramedicos) == Decimal("5")
    assert client.get(f"{ACTIVIDADES}?compromiso_id=999", headers=headers()).json == []

    detalle = client.get(f"{URL}/{compromiso['id']}", headers=headers()).json
    assert detalle["estado"] == "FINALIZADO"
    assert {i["tipo_recurso"]["codigo"]: i["cantidad_liberada"] for i in detalle["items"]} == {
        "PARAMEDICO": "5.00",
        "RESCATISTA": "4.00",
    }
    assert client.get(f"{ACTIVIDADES}/999", headers=headers()).status_code == 404


def test_swagger_documenta_el_token_y_los_errores(client):
    especificacion = client.get("/api/v1/openapi.json").json
    registrar = especificacion["paths"][ACTIVIDADES]["post"]
    assert registrar["security"] == [{"bearerAuth": []}]
    assert {"200", "201", "401", "403", "404", "409", "422"} <= set(registrar["responses"])
