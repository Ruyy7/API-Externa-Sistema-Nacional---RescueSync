def test_lista_solo_habilitadas(client):
    respuesta = client.get("/api/v1/ongs?habilitada=true")
    assert respuesta.status_code == 200
    assert len(respuesta.json) == 2
    assert all(ong["habilitada"] for ong in respuesta.json)


def test_lista_no_habilitadas(client):
    respuesta = client.get("/api/v1/ongs?habilitada=false")
    assert respuesta.status_code == 200
    assert len(respuesta.json) == 1
    assert respuesta.json[0]["estado"] == "PENDIENTE"


def test_detalle_inexistente(client):
    respuesta = client.get("/api/v1/ongs/999999")
    assert respuesta.status_code == 404
    assert respuesta.json["codigo"] == "NO_ENCONTRADO"
