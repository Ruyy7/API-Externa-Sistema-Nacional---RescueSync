"""I-3.4: pedidos simultáneos nunca reservan más de lo que hay (locking en PostgreSQL).

Cada hilo usa su propio cliente y, por lo tanto, su propia conexión a la base, como dos pedidos
reales que llegan a la API al mismo tiempo.
"""

import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import InventarioRecurso
from app.services import servicios
from tests.utiles import URL, headers, inventario, pedido


def _post(app, cuerpo: dict, encabezados: dict, barrera: threading.Barrier | None = None):
    if barrera is not None:
        barrera.wait()
    return app.test_client().post(URL, json=cuerpo, headers=encabezados)


def _retener_fila(fila_id: int):
    """Abre otra conexión y bloquea la fila, como una operación larga en curso."""
    conexion = db.engine.connect()
    transaccion = conexion.begin()
    conexion.execute(
        select(InventarioRecurso.id).where(InventarioRecurso.id == fila_id).with_for_update()
    )
    return conexion, transaccion


def _esperar_sesiones_bloqueadas(cantidad: int, tope_s: float = 5) -> None:
    """Espera hasta que haya `cantidad` sesiones esperando un bloqueo en la base."""
    consulta = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() AND wait_event_type = 'Lock'"
    )
    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as monitor:
        limite = time.monotonic() + tope_s
        while time.monotonic() < limite:
            if monitor.execute(consulta).scalar() >= cantidad:
                return
            time.sleep(0.05)
    raise AssertionError(f"No hubo {cantidad} sesiones esperando el bloqueo")


def test_dos_reservas_simultaneas_no_sobreasignan(app):
    """Los dos pedidos llegan a esperar en el FOR UPDATE: solo uno puede quedarse con 8 de 10."""
    cuerpos = [
        pedido(f"oferta-{n}", items=[("PARAMEDICO", 8)], convocatoria=f"emergencia-{n}")
        for n in (1, 2)
    ]
    encabezados = headers()
    conexion, transaccion = _retener_fila(inventario("PARAMEDICO").id)
    try:
        with ThreadPoolExecutor(max_workers=2) as hilos:
            futuros = [hilos.submit(_post, app, cuerpo, encabezados) for cuerpo in cuerpos]
            _esperar_sesiones_bloqueadas(2)
            transaccion.commit()  # suelta la fila: los dos compiten de verdad
            respuestas = [futuro.result() for futuro in futuros]
    finally:
        conexion.close()

    assert sorted(r.status_code for r in respuestas) == [201, 409]
    rechazada = next(r for r in respuestas if r.status_code == 409)
    assert rechazada.json["codigo"] == "RECURSOS_INSUFICIENTES"
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2 + 8


def test_muchas_reservas_simultaneas_respetan_el_stock(app):
    cuerpos = [
        pedido(f"oferta-{n}", items=[("PARAMEDICO", 3)], convocatoria=f"emergencia-{n}")
        for n in range(6)
    ]
    encabezados, barrera = headers(), threading.Barrier(len(cuerpos))
    with ThreadPoolExecutor(max_workers=len(cuerpos)) as hilos:
        respuestas = list(hilos.map(lambda c: _post(app, c, encabezados, barrera), cuerpos))

    # Hay 10 libres: entran 3 reservas de 3 y las otras 3 se rechazan
    assert Counter(r.status_code for r in respuestas) == {201: 3, 409: 3}
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2 + 9


def test_reservas_cruzadas_no_generan_deadlock(app):
    """Unas piden paramédicos y rescatistas, otras al revés. Como las filas se bloquean siempre
    ordenadas por id, ninguna queda esperando a otra en círculo."""
    cuerpos = [
        pedido(
            f"oferta-{n}",
            items=[("PARAMEDICO", 1), ("RESCATISTA", 1)][:: 1 if n % 2 else -1],
            convocatoria=f"emergencia-{n}",
        )
        for n in range(8)
    ]
    encabezados, barrera = headers(), threading.Barrier(len(cuerpos))
    with ThreadPoolExecutor(max_workers=len(cuerpos)) as hilos:
        respuestas = list(hilos.map(lambda c: _post(app, c, encabezados, barrera), cuerpos))

    assert [r.status_code for r in respuestas] == [201] * 8
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2 + 8
    assert inventario("RESCATISTA").cantidad_bloqueada == 3 + 8


def test_espera_agotada_responde_recurso_ocupado(client, monkeypatch):
    monkeypatch.setattr(servicios().compromisos, "lock_timeout_ms", 200)
    conexion, transaccion = _retener_fila(inventario("PARAMEDICO").id)
    try:
        respuesta = client.post(URL, json=pedido(), headers=headers())
    finally:
        transaccion.rollback()
        conexion.close()
    assert respuesta.status_code == 409
    assert respuesta.json["codigo"] == "RECURSO_OCUPADO"
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2


def test_la_base_rechaza_la_sobreasignacion_aunque_falle_el_codigo():
    fila = inventario("PARAMEDICO")
    with pytest.raises(IntegrityError):
        db.session.execute(
            update(InventarioRecurso)
            .where(InventarioRecurso.id == fila.id)
            .values(cantidad_bloqueada=InventarioRecurso.cantidad_total + 1)
        )
    db.session.rollback()
