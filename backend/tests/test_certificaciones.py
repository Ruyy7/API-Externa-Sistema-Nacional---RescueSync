def test_catalogo_de_certificaciones(client):
    respuesta = client.get("/api/v1/certificaciones")
    assert respuesta.status_code == 200
    codigos = {item["codigo"] for item in respuesta.json}
    assert "PRIMEROS_AUXILIOS" in codigos
    assert "RESCATE_ACUATICO" in codigos


def test_certificaciones_de_ong(client):
    ongs = client.get("/api/v1/ongs?habilitada=true").json
    rescatistas = next(o for o in ongs if o["cuit"] == "30-11111111-1")
    respuesta = client.get(f"/api/v1/ongs/{rescatistas['id']}/certificaciones")
    assert respuesta.status_code == 200
    assert {item["certificacion"]["codigo"] for item in respuesta.json} == {
        "PRIMEROS_AUXILIOS",
        "RESCATE_ACUATICO",
    }
