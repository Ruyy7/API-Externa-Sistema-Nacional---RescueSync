"""Locking pesimista en PostgreSQL para el inventario de las ONGs (I-3.4).

Reglas que evitan deadlocks entre pedidos simultáneos:
1. Una operación sobre un compromiso existente bloquea primero el compromiso y después las filas de
   inventario. Una reserva nueva bloquea solo inventario.
2. Las filas de inventario se bloquean siempre ordenadas por id.

Toda espera por un bloqueo tiene un tope (lock_timeout). Si se agota, o si PostgreSQL igual detecta
un deadlock, la operación responde 409 RECURSO_OCUPADO y el cliente puede reintentar.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import errors as pg
from sqlalchemy import Select, text
from sqlalchemy.exc import OperationalError

from app.errors import RecursoOcupado
from app.extensions import db


def iniciar_transaccion_con_bloqueos(lock_timeout_ms: int) -> None:
    """Cierra la transacción en curso y abre otra con tope de espera por bloqueos.

    SET LOCAL vale solo hasta el fin de la transacción, por eso se ejecuta al empezarla.
    """
    db.session.commit()
    db.session.execute(text(f"SET LOCAL lock_timeout = '{int(lock_timeout_ms)}ms'"))


@contextmanager
def esperando_bloqueos() -> Iterator[None]:
    """Traduce la espera agotada (55P03) o un deadlock (40P01) a un error de dominio."""
    try:
        yield
    except OperationalError as error:
        if isinstance(error.orig, (pg.LockNotAvailable, pg.DeadlockDetected)):
            raise RecursoOcupado(
                "Otra operación está usando estos recursos. Reintentá en unos segundos."
            ) from error
        raise


def bloquear(consulta: Select, *, saltear_ocupadas: bool = False) -> list:
    """SELECT ... FOR UPDATE: las filas quedan bloqueadas hasta el commit o el rollback.

    populate_existing hace que los objetos que ya estaban en la sesión tomen los valores leídos con
    el bloqueo, que son los últimos confirmados.
    """
    consulta = consulta.with_for_update(skip_locked=saltear_ocupadas).execution_options(
        populate_existing=True
    )
    with esperando_bloqueos():
        return list(db.session.scalars(consulta))
