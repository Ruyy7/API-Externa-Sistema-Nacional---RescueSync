"""Atajos para los tests de I-3.4 (bloqueo y compromiso de recursos).

Datos del seed que usan: Rescatistas del Río tiene 12 paramédicos (2 ya bloqueados, 10
disponibles), 20 rescatistas (15 disponibles) y 300 frazadas (250 disponibles), y no tiene
raciones. Ayuda en Registro está PENDIENTE de habilitación.
"""

from datetime import timedelta

from sqlalchemy import select

from app.extensions import db
from app.models import ONG, Convocatoria, InventarioRecurso, TipoRecurso
from app.models.comun import ahora
from app.security import RolSistema, emitir_token

RIO = "30-11111111-1"
PENDIENTE = "30-33333333-3"

URL = "/api/v1/compromisos"


def headers(rol: RolSistema = RolSistema.WEBAPP) -> dict:
    return {"Authorization": f"Bearer {emitir_token('tests', rol)}"}


def inventario(codigo: str, cuit: str = RIO) -> InventarioRecurso:
    """La fila tal como está confirmada en la base (sin lo que haya quedado en la sesión)."""
    db.session.expire_all()
    consulta = (
        select(InventarioRecurso)
        .join(InventarioRecurso.ong)
        .join(InventarioRecurso.tipo_recurso)
        .where(ONG.cuit == cuit, TipoRecurso.codigo == codigo)
    )
    return db.session.scalar(consulta)


def pedido(
    oferta: str = "oferta-1",
    *,
    items=(("PARAMEDICO", 5),),
    convocatoria: str = "conv-1",
    emergencia: str = "emergencia-1",
    cuit: str = RIO,
    cierre: timedelta = timedelta(hours=2),
    limite: timedelta = timedelta(days=2),
) -> dict:
    """Cuerpo de una reserva. cierre y limite son relativos a ahora."""
    return {
        "oferta_referencia": oferta,
        "ong_cuit": cuit,
        "convocatoria": {
            "referencia": convocatoria,
            "emergencia_referencia": emergencia,
            "fecha_cierre": (ahora() + cierre).isoformat(),
            "fecha_limite_adjudicacion": (ahora() + limite).isoformat(),
        },
        "items": [{"tipo_recurso": codigo, "cantidad": cantidad} for codigo, cantidad in items],
    }


def reservar(client, oferta: str = "oferta-1", **kwargs):
    return client.post(URL, json=pedido(oferta, **kwargs), headers=headers())


def reserva_creada(client, oferta: str = "oferta-1", **kwargs) -> dict:
    respuesta = reservar(client, oferta, **kwargs)
    assert respuesta.status_code == 201, respuesta.json
    return respuesta.json


def confirmar(client, compromiso_id: int, items):
    cuerpo = {"items": [{"tipo_recurso": codigo, "cantidad": n} for codigo, n in items]}
    return client.post(
        f"{URL}/{compromiso_id}/confirmacion", json=cuerpo, headers=headers(RolSistema.BONITA)
    )


def mover_fechas(referencia: str, *, cierre: timedelta, limite: timedelta) -> None:
    """Simula que pasó el tiempo: fechas relativas a ahora (negativas = en el pasado)."""
    convocatoria = db.session.scalar(
        select(Convocatoria).where(Convocatoria.referencia == referencia)
    )
    convocatoria.fecha_cierre = ahora() + cierre
    convocatoria.fecha_limite_adjudicacion = ahora() + limite
    db.session.commit()


def por_tipo(compromiso: dict) -> dict:
    """{codigo: (reservada, comprometida)} a partir de la respuesta de la API."""
    return {
        item["tipo_recurso"]["codigo"]: (item["cantidad_reservada"], item["cantidad_comprometida"])
        for item in compromiso["items"]
    }
