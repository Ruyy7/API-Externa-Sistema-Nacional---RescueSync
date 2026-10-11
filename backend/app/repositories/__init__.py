"""Patrón Repository: consultas SQLAlchemy aisladas de la capa de servicios."""

from sqlalchemy import Select, func, select

from app.extensions import db


def paginar(consulta: Select, pagina: int, tamano: int) -> tuple[list, int]:
    total = db.session.scalar(select(func.count()).select_from(consulta.order_by(None).subquery()))
    elementos = db.session.execute(
        consulta.limit(tamano).offset((pagina - 1) * tamano)
    ).all()
    return list(elementos), int(total or 0)


def paginar_entidades(consulta: Select, pagina: int, tamano: int) -> tuple[list, int]:
    total = db.session.scalar(select(func.count()).select_from(consulta.order_by(None).subquery()))
    elementos = db.session.scalars(consulta.limit(tamano).offset((pagina - 1) * tamano)).all()
    return list(elementos), int(total or 0)
