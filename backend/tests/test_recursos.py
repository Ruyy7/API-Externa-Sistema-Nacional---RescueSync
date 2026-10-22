from decimal import Decimal

from tests.utiles import headers


def _por_codigo(items, codigo):
    return next(item for item in items if item["tipo_recurso"]["codigo"] == codigo)


def _id_de_ong(client, cuit):
    ongs = client.get("/api/v1/ongs?page_size=100", headers=headers()).json
    return next(o["id"] for o in ongs if o["cuit"] == cuit)


def test_disponibilidad_global_excluye_ong_pendiente(client):
    respuesta = client.get("/api/v1/recursos/disponibilidad")
    assert respuesta.status_code == 200
    paramedicos = _por_codigo(respuesta.json, "PARAMEDICO")
    assert Decimal(paramedicos["cantidad_total"]) == Decimal("12.00")
    assert Decimal(paramedicos["cantidad_bloqueada"]) == Decimal("2.00")
    assert Decimal(paramedicos["cantidad_comprometida"]) == Decimal("0.00")
    assert Decimal(paramedicos["cantidad_disponible"]) == Decimal("10.00")


def test_disponibilidad_puede_incluir_no_habilitadas(client):
    respuesta = client.get("/api/v1/recursos/disponibilidad?solo_ongs_habilitadas=false")
    assert respuesta.status_code == 200
    paramedicos = _por_codigo(respuesta.json, "PARAMEDICO")
    assert Decimal(paramedicos["cantidad_total"]) == Decimal("112.00")
    assert Decimal(paramedicos["cantidad_disponible"]) == Decimal("110.00")


def test_inventario_por_ong_distingue_reserva_y_compromiso(client):
    ong_id = _id_de_ong(client, "30-22222222-2")
    respuesta = client.get(f"/api/v1/ongs/{ong_id}/recursos")
    assert respuesta.status_code == 200
    raciones = _por_codigo(respuesta.json, "RACION_ALIMENTO")
    assert Decimal(raciones["cantidad_bloqueada"]) == Decimal("700.00")
    assert Decimal(raciones["cantidad_comprometida"]) == Decimal("300.00")
    assert Decimal(raciones["cantidad_disponible"]) == Decimal("4000.00")


def test_tipo_recurso_indica_si_vuelve_al_stock(client):
    respuesta = client.get("/api/v1/tipos-recursos?page_size=100")
    assert respuesta.status_code == 200
    carpa = next(item for item in respuesta.json if item["codigo"] == "CARPA")
    racion = next(item for item in respuesta.json if item["codigo"] == "RACION_ALIMENTO")
    assert carpa["reutilizable"] is True
    assert racion["reutilizable"] is False


def test_disponibilidad_filtrada_por_ong(client):
    ong_id = _id_de_ong(client, "30-22222222-2")
    respuesta = client.get(f"/api/v1/recursos/disponibilidad?ong_id={ong_id}")
    assert respuesta.status_code == 200
    assert {item["tipo_recurso"]["codigo"] for item in respuesta.json} == {
        "RACION_ALIMENTO",
        "AGUA_POTABLE",
        "ALIMENTO_SECO",
    }


def test_disponibilidad_de_ong_no_habilitada_pide_incluirlas(client):
    ong_id = _id_de_ong(client, "30-33333333-3")
    respuesta = client.get(f"/api/v1/recursos/disponibilidad?ong_id={ong_id}")
    assert respuesta.status_code == 422
    assert respuesta.json["codigo"] == "VALIDACION"

    respuesta = client.get(
        f"/api/v1/recursos/disponibilidad?ong_id={ong_id}&solo_ongs_habilitadas=false"
    )
    assert respuesta.status_code == 200
    assert Decimal(_por_codigo(respuesta.json, "PARAMEDICO")["cantidad_total"]) == Decimal("100")


def test_disponibilidad_con_ong_o_tipo_inexistente(client):
    respuesta = client.get("/api/v1/recursos/disponibilidad?ong_id=999999")
    assert respuesta.status_code == 404
    respuesta = client.get("/api/v1/recursos/disponibilidad?tipo_recurso_id=999")
    assert respuesta.status_code == 404
    assert respuesta.json["codigo"] == "NO_ENCONTRADO"


def test_disponibilidad_con_parametros_invalidos(client):
    for consulta in ("ong_id=abc", "tipo_recurso_id=x", "solo_ong_habilitadas=false", "page=0"):
        respuesta = client.get(f"/api/v1/recursos/disponibilidad?{consulta}")
        assert respuesta.status_code == 422, consulta
        assert respuesta.json["codigo"] == "VALIDACION"


def test_inventario_de_ong_inexistente(client):
    respuesta = client.get("/api/v1/ongs/999999/recursos")
    assert respuesta.status_code == 404
