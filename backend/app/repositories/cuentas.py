from collections.abc import Collection

from sqlalchemy import select

from app.extensions import db
from app.models import CompromisoItem, Cuenta, InventarioRecurso


class CuentaRepository:
    def agregar(self, cuenta: Cuenta) -> None:
        db.session.add(cuenta)

    def por_usuario(self, usuario: str) -> Cuenta | None:
        return db.session.scalar(select(Cuenta).where(Cuenta.usuario == usuario))


class CategoriaRepository:
    """Categorías de una ONG: sus filas de `inventario_recurso` (docs/03, correo del 08/10)."""

    def de_ong(self, ong_id: int) -> list[InventarioRecurso]:
        consulta = (
            select(InventarioRecurso)
            .where(InventarioRecurso.ong_id == ong_id)
            .order_by(InventarioRecurso.id)
        )
        return list(db.session.scalars(consulta))

    def con_historial(self, inventario_ids: Collection[int]) -> set[int]:
        """Categorías que alguna reserva usó: no se borran porque compromiso_item las referencia."""
        consulta = select(CompromisoItem.inventario_recurso_id).where(
            CompromisoItem.inventario_recurso_id.in_(inventario_ids)
        )
        return set(db.session.scalars(consulta))
