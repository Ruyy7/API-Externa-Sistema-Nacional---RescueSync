from decimal import Decimal


def _por_codigo(items, codigo):
    return next(item for item in items if item["tipo_recurso"]["codigo"] == codigo)


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
    ongs = client.get("/api/v1/ongs?habilitada=true").json
    ong = next(o for o in ongs if o["cuit"] == "30-22222222-2")
    respuesta = client.get(f"/api/v1/ongs/{ong['id']}/recursos")
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
