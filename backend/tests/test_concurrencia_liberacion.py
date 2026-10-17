"""I-3.5: liberaciones simultáneas nunca liberan de más ni dos veces (locking en PostgreSQL).

Mismo esquema que tests/test_concurrencia.py: cada hilo usa su propio cliente (y, por lo tanto, su
propia conexión), y una conexión aparte retiene la fila de inventario hasta que los pedidos están
esperando el bloqueo, así compiten de verdad. Los pedidos se mandan de a uno, y cada uno llega a
esperar un bloqueo antes de mandar el siguiente: el orden en que los toman es conocido.
"""

from concurrent.futures import ThreadPoolExecutor

from app.security import RolSistema
from app.services import servicios
from tests.test_concurrencia import _esperar_sesiones_bloqueadas, _retener_fila
from tests.test_liberaciones import (
    ACTIVIDADES,
    EMERGENCIA,
    actividad,
    cantidad_de_actividades,
    comprometido,
    contadores,
)
from tests.utiles import URL, headers, inventario, pedido


def _post(app, url: str, cuerpo: dict, encabezados: dict):
    return app.test_client().post(url, json=cuerpo, headers=encabezados)


def _escalonados(app, fila_id: int, pedidos: list[tuple[str, dict, dict]]) -> list:
    """Retiene la fila, manda los pedidos de a uno (cada uno queda esperando un bloqueo antes de
    mandar el siguiente) y recién ahí suelta la fila."""
    conexion, transaccion = _retener_fila(fila_id)
    try:
        with ThreadPoolExecutor(max_workers=len(pedidos)) as hilos:
            futuros = []
            for numero, (url, cuerpo, encabezados) in enumerate(pedidos, 1):
                futuros.append(hilos.submit(_post, app, url, cuerpo, encabezados))
                _esperar_sesiones_bloqueadas(numero)
            transaccion.commit()  # suelta la fila: ahora compiten de verdad
            return [futuro.result() for futuro in futuros]
    finally:
        conexion.close()


def test_dos_actividades_no_liberan_mas_de_lo_pendiente(app, client):
    """Quedan 5 paramédicos pendientes y llegan dos actividades de 3: entra una sola.

    La primera toma el compromiso y espera el inventario; la segunda espera el compromiso. Cuando
    la segunda lo toma, relee el ítem (ya con 3 liberados) y ve que no alcanza.
    """
    comprometido(client)
    webapp = headers()

    respuestas = _escalonados(
        app,
        inventario("PARAMEDICO").id,
        [
            (ACTIVIDADES, actividad("ACT-1", cantidad=3), webapp),
            (ACTIVIDADES, actividad("ACT-2", cantidad=3), webapp),
        ],
    )

    assert [r.status_code for r in respuestas] == [201, 409]
    assert respuestas[1].json["codigo"] == "EXCEDE_PENDIENTE"
    assert contadores("PARAMEDICO") == (12, 2, 2)
    assert cantidad_de_actividades() == 1


def test_el_mismo_pedido_en_paralelo_libera_una_sola_vez(app, client):
    """La webapp reintenta antes de recibir la respuesta: el segundo encuentra la actividad."""
    comprometido(client)
    cuerpo, webapp = actividad(cantidad=3), headers()

    respuestas = _escalonados(app, inventario("PARAMEDICO").id, [(ACTIVIDADES, cuerpo, webapp)] * 2)

    assert [r.status_code for r in respuestas] == [201, 200]
    assert respuestas[0].json["id"] == respuestas[1].json["id"]
    assert contadores("PARAMEDICO") == (12, 2, 2)
    assert cantidad_de_actividades() == 1


def test_liberar_y_reservar_a_la_vez_dejan_los_contadores_coherentes(app, client):
    """Una actividad (punto 5) y una reserva nueva (punto 4) compiten por la misma fila."""
    comprometido(client)

    respuestas = _escalonados(
        app,
        inventario("PARAMEDICO").id,
        [
            (ACTIVIDADES, actividad(cantidad=3), headers()),
            (URL, pedido("oferta-2", items=[("PARAMEDICO", 4)], convocatoria="conv-2"), headers()),
        ],
    )

    assert [r.status_code for r in respuestas] == [201, 201]
    assert contadores("PARAMEDICO") == (12, 2 + 4, 5 - 3)


def test_el_cierre_espera_a_la_actividad_en_curso(app, client):
    """El cierre bloquea el compromiso que la actividad está liberando, así que decide con el
    estado final: la actividad lo deja FINALIZADO y el cierre entra."""
    comprometido(client)

    respuestas = _escalonados(
        app,
        inventario("PARAMEDICO").id,
        [
            (ACTIVIDADES, actividad(cantidad=5), headers()),
            (f"{EMERGENCIA}/cierre", {}, headers(RolSistema.BONITA)),
        ],
    )

    assert [r.status_code for r in respuestas] == [201, 201]
    assert respuestas[0].json["estado_compromiso"] == "FINALIZADO"
    assert respuestas[1].json["emergencia_referencia"] == "emergencia-1"
    assert contadores("PARAMEDICO") == (12, 2, 0)


def test_espera_agotada_responde_recurso_ocupado_sin_liberar(client, monkeypatch):
    comprometido(client)
    monkeypatch.setattr(servicios().liberaciones, "lock_timeout_ms", 200)
    conexion, transaccion = _retener_fila(inventario("PARAMEDICO").id)
    try:
        respuesta = client.post(ACTIVIDADES, json=actividad(), headers=headers())
    finally:
        transaccion.rollback()
        conexion.close()
    assert (respuesta.status_code, respuesta.json["codigo"]) == (409, "RECURSO_OCUPADO")
    assert contadores("PARAMEDICO") == (12, 2, 5)
    assert cantidad_de_actividades() == 0
