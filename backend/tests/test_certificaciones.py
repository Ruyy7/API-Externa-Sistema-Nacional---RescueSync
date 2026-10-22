from tests.utiles import headers


def test_catalogo_de_certificaciones(client):
    respuesta = client.get("/api/v1/certificaciones")
    assert respuesta.status_code == 200
    codigos = {item["codigo"] for item in respuesta.json}
    assert "PRIMEROS_AUXILIOS" in codigos
    assert "RESCATE_ACUATICO" in codigos


def test_certificaciones_de_ong(client):
    ongs = client.get("/api/v1/ongs?habilitada=true", headers=headers()).json
    rescatistas = next(o for o in ongs if o["cuit"] == "30-11111111-1")
    respuesta = client.get(
        f"/api/v1/ongs/{rescatistas['id']}/certificaciones", headers=headers()
    )
    assert respuesta.status_code == 200
    assert {item["certificacion"]["codigo"] for item in respuesta.json} == {
        "PRIMEROS_AUXILIOS",
        "RESCATE_ACUATICO",
    }


def test_certificaciones_de_ong_inexistente(client):
    respuesta = client.get("/api/v1/ongs/999999/certificaciones", headers=headers())
    assert respuesta.status_code == 404
    assert respuesta.json["codigo"] == "NO_ENCONTRADO"


def test_filtro_desconocido_en_certificaciones(client):
    respuesta = client.get("/api/v1/certificaciones?activas=false")
    assert respuesta.status_code == 422
