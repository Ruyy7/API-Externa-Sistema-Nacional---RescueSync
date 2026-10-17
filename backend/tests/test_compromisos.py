"""I-3.4: validar restricciones, reservar, ajustar, cancelar, confirmar y vencer recursos."""

from datetime import timedelta
from decimal import Decimal

from app.security import RolSistema
from tests.utiles import (
    PENDIENTE,
    RIO,
    URL,
    confirmar,
    headers,
    inventario,
    mover_fechas,
    pedido,
    por_tipo,
    reserva_creada,
    reservar,
)

# --- Validar restricciones -------------------------------------------------------------------


def test_verificacion_detalla_por_item_sin_reservar(client):
    cuerpo = {
        "ong_cuit": RIO,
        "items": [
            {"tipo_recurso": "PARAMEDICO", "cantidad": 15},
            {"tipo_recurso": "RESCATISTA", "cantidad": 5},
            {"tipo_recurso": "RACION_ALIMENTO", "cantidad": 1},
        ],
    }
    respuesta = client.post(f"{URL}/verificacion", json=cuerpo, headers=headers())
    assert respuesta.status_code == 200
    assert respuesta.json["ong_habilitada"] is True
    assert respuesta.json["se_puede_reservar"] is False
    resultados = {item["tipo_recurso"]: item for item in respuesta.json["items"]}
    assert resultados["PARAMEDICO"]["resultado"] == "PARCIAL"
    assert Decimal(resultados["PARAMEDICO"]["disponible"]) == 10
    assert resultados["RESCATISTA"]["resultado"] == "DISPONIBLE"
    assert resultados["RACION_ALIMENTO"]["resultado"] == "SIN_DISPONIBILIDAD"
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2  # no reservó nada


def test_verificacion_informa_ong_no_habilitada(client):
    cuerpo = {"ong_cuit": PENDIENTE, "items": [{"tipo_recurso": "PARAMEDICO", "cantidad": 1}]}
    respuesta = client.post(f"{URL}/verificacion", json=cuerpo, headers=headers())
    assert respuesta.status_code == 200
    assert respuesta.json["ong_habilitada"] is False
    assert respuesta.json["se_puede_reservar"] is False


# --- Reservar ----------------------------------------------------------------------------------


def test_reserva_bloquea_los_recursos(client):
    respuesta = reservar(client)
    assert respuesta.status_code == 201
    assert respuesta.json["estado"] == "RESERVADO"
    assert respuesta.json["creado_por"] == "tests"
    assert respuesta.json["ong"]["cuit"] == RIO
    assert respuesta.json["convocatoria"]["emergencia_referencia"] == "emergencia-1"
    assert por_tipo(respuesta.json) == {"PARAMEDICO": ("5.00", "0.00")}
    assert inventario("PARAMEDICO").cantidad_bloqueada == 7


def test_reserva_repetida_no_reserva_dos_veces(client):
    primera = reservar(client)
    segunda = reservar(client)
    assert (primera.status_code, segunda.status_code) == (201, 200)
    assert segunda.json["id"] == primera.json["id"]
    assert inventario("PARAMEDICO").cantidad_bloqueada == 7


def test_misma_oferta_con_otro_pedido_choca(client):
    reserva_creada(client)
    respuesta = reservar(client, items=[("PARAMEDICO", 6)])
    assert respuesta.status_code == 409
    assert respuesta.json["codigo"] == "COMPROMISO_EXISTENTE"


def test_sin_disponibilidad_no_reserva_nada(client):
    respuesta = reservar(client, items=[("PARAMEDICO", 11), ("RESCATISTA", 1)])
    assert respuesta.status_code == 409
    assert respuesta.json["codigo"] == "RECURSOS_INSUFICIENTES"
    assert respuesta.json["detalles"]["items"] == [
        {"tipo_recurso": "PARAMEDICO", "solicitado": "11.00", "disponible": "10.00"}
    ]
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2
    assert inventario("RESCATISTA").cantidad_bloqueada == 3
    assert client.get(URL, headers=headers()).json == []


def test_recurso_que_la_ong_no_tiene_cuenta_como_cero(client):
    respuesta = reservar(client, items=[("RACION_ALIMENTO", 1)])
    assert respuesta.status_code == 409
    assert respuesta.json["detalles"]["items"][0]["disponible"] == "0"


def test_ong_no_habilitada_no_reserva(client):
    respuesta = reservar(client, cuit=PENDIENTE)
    assert respuesta.status_code == 422
    assert respuesta.json["codigo"] == "ONG_NO_HABILITADA"


def test_ong_inexistente(client):
    cuerpo = pedido() | {"ong_cuit": "30-99999999-9"}
    respuesta = client.post(URL, json=cuerpo, headers=headers())
    assert respuesta.status_code == 422
    assert respuesta.json["codigo"] == "ONG_INEXISTENTE"
    assert "ong_cuit" in respuesta.json["detalles"]["json"]


def test_items_invalidos(client):
    items = [("NO_EXISTE", 1), ("PARAMEDICO", Decimal("1.5")), ("FRAZADA", 1), ("FRAZADA", 2)]
    cuerpo = pedido(items=[(codigo, str(cantidad)) for codigo, cantidad in items])
    respuesta = client.post(URL, json=cuerpo, headers=headers())
    assert respuesta.status_code == 422
    errores = respuesta.json["detalles"]["json"]["items"]
    assert set(errores) == {"0", "1", "3"}
    assert "cantidad" in errores["1"]  # los paramédicos no se fraccionan


def test_ventana_cerrada_no_reserva(client):
    respuesta = reservar(client, cierre=timedelta(hours=-1))
    assert respuesta.status_code == 409
    assert respuesta.json["codigo"] == "VENTANA_CERRADA"


# --- Ajustar y cancelar --------------------------------------------------------------------------


def test_ajuste_aumenta_reduce_quita_y_agrega(client):
    compromiso = reserva_creada(client, items=[("PARAMEDICO", 5), ("RESCATISTA", 2)])
    nuevo = {
        "items": [
            {"tipo_recurso": "PARAMEDICO", "cantidad": 3},
            {"tipo_recurso": "FRAZADA", "cantidad": 10},
        ]
    }
    respuesta = client.put(f"{URL}/{compromiso['id']}", json=nuevo, headers=headers())
    assert respuesta.status_code == 200
    assert por_tipo(respuesta.json) == {
        "PARAMEDICO": ("3.00", "0.00"),
        "FRAZADA": ("10.00", "0.00"),
    }
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2 + 3
    assert inventario("RESCATISTA").cantidad_bloqueada == 3  # volvió lo reservado
    assert inventario("FRAZADA").cantidad_bloqueada == 20 + 10


def test_ajuste_sin_disponibilidad_deja_la_reserva_como_estaba(client):
    compromiso = reserva_creada(client)
    nuevo = {"items": [{"tipo_recurso": "PARAMEDICO", "cantidad": 16}]}
    respuesta = client.put(f"{URL}/{compromiso['id']}", json=nuevo, headers=headers())
    assert respuesta.status_code == 409
    assert respuesta.json["detalles"]["items"][0]["solicitado"] == "11.00"  # lo que aumenta
    assert inventario("PARAMEDICO").cantidad_bloqueada == 7
    detalle = client.get(f"{URL}/{compromiso['id']}", headers=headers()).json
    assert por_tipo(detalle) == {"PARAMEDICO": ("5.00", "0.00")}


def test_ajuste_con_la_ventana_cerrada(client):
    compromiso = reserva_creada(client)
    mover_fechas("conv-1", cierre=timedelta(hours=-1), limite=timedelta(days=1))
    nuevo = {"items": [{"tipo_recurso": "PARAMEDICO", "cantidad": 1}]}
    respuesta = client.put(f"{URL}/{compromiso['id']}", json=nuevo, headers=headers())
    assert respuesta.status_code == 409
    assert respuesta.json["codigo"] == "VENTANA_CERRADA"


def test_cancelacion_libera_y_se_puede_repetir(client):
    compromiso = reserva_creada(client)
    for _ in range(2):
        respuesta = client.post(f"{URL}/{compromiso['id']}/cancelacion", headers=headers())
        assert respuesta.status_code == 200
        assert respuesta.json["estado"] == "CANCELADO"
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2


# --- Confirmar lo adjudicado ---------------------------------------------------------------------


def test_adjudicacion_parcial_compromete_y_libera_la_diferencia(client):
    compromiso = reserva_creada(client, items=[("PARAMEDICO", 5), ("RESCATISTA", 4)])
    respuesta = confirmar(client, compromiso["id"], [("PARAMEDICO", 3)])
    assert respuesta.status_code == 200
    assert respuesta.json["estado"] == "COMPROMETIDO"
    assert respuesta.json["confirmado_en"] is not None
    assert por_tipo(respuesta.json) == {
        "PARAMEDICO": ("5.00", "3.00"),
        "RESCATISTA": ("4.00", "0.00"),
    }
    paramedicos, rescatistas = inventario("PARAMEDICO"), inventario("RESCATISTA")
    assert (paramedicos.cantidad_bloqueada, paramedicos.cantidad_comprometida) == (2, 3)
    assert (rescatistas.cantidad_bloqueada, rescatistas.cantidad_comprometida) == (3, 2)


def test_confirmacion_repetida(client):
    compromiso = reserva_creada(client)
    assert confirmar(client, compromiso["id"], [("PARAMEDICO", 5)]).status_code == 200
    assert confirmar(client, compromiso["id"], [("PARAMEDICO", 5)]).status_code == 200
    otra = confirmar(client, compromiso["id"], [("PARAMEDICO", 4)])
    assert otra.status_code == 409
    assert otra.json["codigo"] == "TRANSICION_INVALIDA"
    assert inventario("PARAMEDICO").cantidad_comprometida == 5


def test_confirmacion_valida_las_cantidades(client):
    compromiso = reserva_creada(client)
    for items in ([("PARAMEDICO", 6)], [("RESCATISTA", 1)], [("PARAMEDICO", 0)]):
        respuesta = confirmar(client, compromiso["id"], items)
        assert respuesta.status_code == 422, items
    assert inventario("PARAMEDICO").cantidad_comprometida == 0


def test_no_se_cancela_lo_adjudicado(client):
    compromiso = reserva_creada(client)
    confirmar(client, compromiso["id"], [("PARAMEDICO", 5)])
    respuesta = client.post(f"{URL}/{compromiso['id']}/cancelacion", headers=headers())
    assert respuesta.status_code == 409
    assert respuesta.json["codigo"] == "TRANSICION_INVALIDA"


# --- Vencimiento ---------------------------------------------------------------------------------


def test_adjudicar_despues_del_limite_vence_la_reserva(client):
    compromiso = reserva_creada(client)
    mover_fechas("conv-1", cierre=timedelta(days=-2), limite=timedelta(hours=-1))
    respuesta = confirmar(client, compromiso["id"], [("PARAMEDICO", 5)])
    assert respuesta.status_code == 409
    assert respuesta.json["codigo"] == "RESERVA_VENCIDA"
    detalle = client.get(f"{URL}/{compromiso['id']}", headers=headers()).json
    assert detalle["estado"] == "VENCIDO"
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2


def test_la_reserva_sigue_bloqueada_entre_el_cierre_y_el_limite(client):
    compromiso = reserva_creada(client)
    mover_fechas("conv-1", cierre=timedelta(hours=-1), limite=timedelta(days=1))
    otra = reservar(client, "oferta-2", items=[("PARAMEDICO", 6)], convocatoria="conv-2")
    assert otra.status_code == 409  # quedan 5 libres: los otros 5 siguen reservados
    assert confirmar(client, compromiso["id"], [("PARAMEDICO", 5)]).status_code == 200


def test_comando_vence_las_reservas_atrasadas(app, client):
    vieja = reserva_creada(client, items=[("PARAMEDICO", 2)])
    vigente = reserva_creada(client, "oferta-2", items=[("PARAMEDICO", 3)], convocatoria="conv-2")
    mover_fechas("conv-1", cierre=timedelta(days=-2), limite=timedelta(hours=-1))
    resultado = app.test_cli_runner().invoke(args=["vencer-reservas"])
    assert "Reservas vencidas: 1." in resultado.output
    assert client.get(f"{URL}/{vieja['id']}", headers=headers()).json["estado"] == "VENCIDO"
    assert client.get(f"{URL}/{vigente['id']}", headers=headers()).json["estado"] == "RESERVADO"
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2 + 3


def test_una_reserva_nueva_vence_las_atrasadas_del_mismo_recurso(client):
    reserva_creada(client, items=[("PARAMEDICO", 10)])
    mover_fechas("conv-1", cierre=timedelta(days=-2), limite=timedelta(hours=-1))
    nueva = reservar(client, "oferta-2", items=[("PARAMEDICO", 10)], convocatoria="conv-2")
    assert nueva.status_code == 201


# --- Consultas -------------------------------------------------------------------------------


def test_listado_filtra_y_detalle_inexistente(client):
    reserva_creada(client)
    cancelada = reserva_creada(client, "oferta-2", items=[("RESCATISTA", 1)])
    client.post(f"{URL}/{cancelada['id']}/cancelacion", headers=headers())
    auditor = headers(RolSistema.AUDITOR)
    reservados = client.get(f"{URL}?estado=RESERVADO", headers=auditor).json
    assert [c["oferta_referencia"] for c in reservados] == ["oferta-1"]
    assert len(client.get(f"{URL}?convocatoria=conv-1", headers=auditor).json) == 2
    assert len(client.get(f"{URL}?emergencia=emergencia-1", headers=auditor).json) == 2
    assert len(client.get(f"{URL}?emergencia=otra", headers=auditor).json) == 0
    assert len(client.get(f"{URL}?ong_cuit={RIO}", headers=auditor).json) == 2
    assert len(client.get(f"{URL}?ong_cuit={PENDIENTE}", headers=auditor).json) == 0
    respuesta = client.get(f"{URL}/999999", headers=auditor)
    assert respuesta.status_code == 404
