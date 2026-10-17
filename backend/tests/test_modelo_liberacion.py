"""Lo que el modelo de I-3.4 le deja listo a la liberación (I-3.5), y lo que I-3.5 le agrega.

No hay endpoint de liberación acá: estos tests fijan el contrato del modelo que ese punto usa,
para que un cambio en el modelo lo rompa antes de llegar a su código.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.errors import TransicionInvalida
from app.extensions import db
from app.models import Compromiso, EstadoCompromiso, UnidadMedida
from tests.utiles import URL, confirmar, headers, inventario, reserva_creada


def _comprometido(client, cantidad: int = 4) -> int:
    compromiso = reserva_creada(client, items=[("PARAMEDICO", cantidad)])
    assert confirmar(client, compromiso["id"], [("PARAMEDICO", cantidad)]).status_code == 200
    return compromiso["id"]


def test_liberar_y_consumir_descuentan_lo_comprometido(client):
    _comprometido(client)
    fila = inventario("PARAMEDICO")
    assert (fila.cantidad_total, fila.cantidad_comprometida) == (12, 4)
    fila.liberar(Decimal("1"))  # un reutilizable vuelve al stock
    fila.consumir(Decimal("1"))  # un consumible sale del stock
    db.session.commit()
    fila = inventario("PARAMEDICO")
    assert (fila.cantidad_total, fila.cantidad_bloqueada, fila.cantidad_comprometida) == (11, 2, 2)


def test_finalizar_registra_la_fecha(client):
    compromiso_id = _comprometido(client)
    compromiso = db.session.get(Compromiso, compromiso_id)
    compromiso.transicionar(EstadoCompromiso.FINALIZADO)
    db.session.commit()
    detalle = client.get(f"{URL}/{compromiso_id}", headers=headers()).json
    assert detalle["estado"] == "FINALIZADO"
    assert detalle["finalizado_en"] is not None


def test_solo_se_finaliza_lo_comprometido(client):
    reserva = reserva_creada(client)
    compromiso = db.session.get(Compromiso, reserva["id"])
    with pytest.raises(TransicionInvalida):
        compromiso.transicionar(EstadoCompromiso.FINALIZADO)
    db.session.rollback()


def test_la_base_exige_la_fecha_de_finalizacion(client):
    compromiso_id = _comprometido(client)
    with pytest.raises(IntegrityError):
        db.session.execute(
            text("UPDATE compromiso SET estado = 'FINALIZADO' WHERE id = :id"),
            {"id": compromiso_id},
        )
    db.session.rollback()


# --- Lo que agrega I-3.5 al modelo -----------------------------------------------------------


def test_lo_pendiente_es_lo_comprometido_menos_lo_liberado(client):
    compromiso = db.session.get(Compromiso, _comprometido(client))
    [item] = compromiso.items
    assert (item.cantidad_liberada, item.cantidad_pendiente) == (0, 4)
    assert not compromiso.todo_liberado()
    item.cantidad_liberada = Decimal("4")
    assert item.cantidad_pendiente == 0
    assert compromiso.todo_liberado()
    db.session.rollback()


def test_la_base_impide_liberar_mas_de_lo_comprometido(client):
    compromiso_id = _comprometido(client)
    with pytest.raises(IntegrityError):
        db.session.execute(
            text(
                "UPDATE compromiso_item SET cantidad_liberada = cantidad_comprometida + 1 "
                "WHERE compromiso_id = :id"
            ),
            {"id": compromiso_id},
        )
    db.session.rollback()


@pytest.mark.parametrize(
    ("unidad", "cantidad", "admite"),
    [("PERSONA", "3", True), ("PERSONA", "2.5", False), ("LITRO", "2.5", True)],
)
def test_la_unidad_decide_si_admite_decimales(unidad, cantidad, admite):
    fila = db.session.scalar(select(UnidadMedida).where(UnidadMedida.codigo == unidad))
    assert fila.admite(Decimal(cantidad)) is admite
