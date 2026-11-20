from collections.abc import Collection

from sqlalchemy import and_, or_, select

from app.extensions import db
from app.models import InventarioRecurso, TipoRecurso
from app.repositories.bloqueos import bloquear


class InventarioRepository:
    """Lecturas y bloqueos del inventario que usan las operaciones de I-3.4."""

    def tipos_por_codigo(self, codigos: Collection[str]) -> dict[str, TipoRecurso]:
        consulta = select(TipoRecurso).where(TipoRecurso.codigo.in_(codigos))
        return {tipo.codigo: tipo for tipo in db.session.scalars(consulta)}

    def de_ong(self, ong_id: int, tipo_ids: Collection[int]) -> dict[int, InventarioRecurso]:
        """Sin bloqueo: para consultar o para decidir qué filas bloquear después."""
        consulta = select(InventarioRecurso).where(
            InventarioRecurso.ong_id == ong_id, InventarioRecurso.tipo_recurso_id.in_(tipo_ids)
        )
        return {fila.tipo_recurso_id: fila for fila in db.session.scalars(consulta)}

    def bloquear_de_ong(
        self, ong_id: int, tipo_ids: Collection[int]
    ) -> dict[int, InventarioRecurso]:
        """Bloquea las filas de la ONG para esos tipos de recurso. Devuelve {tipo_recurso_id: fila}.

        Un tipo sin fila no aparece: la ONG no tiene ese recurso (disponible = 0).
        """
        consulta = (
            select(InventarioRecurso)
            .where(
                InventarioRecurso.ong_id == ong_id,
                InventarioRecurso.tipo_recurso_id.in_(tipo_ids),
            )
            .order_by(InventarioRecurso.id)
        )
        return {fila.tipo_recurso_id: fila for fila in bloquear(consulta)}

    def bloquear_por_ids(self, ids: Collection[int]) -> dict[int, InventarioRecurso]:
        """Bloquea las filas indicadas, en orden de id. Devuelve {id: fila}."""
        consulta = (
            select(InventarioRecurso)
            .where(InventarioRecurso.id.in_(ids))
            .order_by(InventarioRecurso.id)
        )
        return {fila.id: fila for fila in bloquear(consulta)}

    def ids_de_ongs(self, ong_ids: Collection[int], tipo_ids: Collection[int]) -> list[int]:
        """Sin bloqueo: ids de las filas de esas ONGs para esos tipos de recurso."""
        consulta = select(InventarioRecurso.id).where(
            InventarioRecurso.ong_id.in_(ong_ids),
            InventarioRecurso.tipo_recurso_id.in_(tipo_ids),
        )
        return list(db.session.scalars(consulta))

    def bloquear_de_ongs(
        self,
        ong_ids: Collection[int],
        tipo_ids: Collection[int],
        *,
        ademas: Collection[int] = (),
    ) -> dict[int, InventarioRecurso]:
        """Bloquea en una sola consulta, en orden de id, las filas de varias ONGs para esos tipos
        de recurso y las filas de `ademas` (ids). Devuelve {id: fila}.

        Lo usan las operaciones en lote de Bonita, que tocan el inventario de todas las ONGs de
        una convocatoria: tomar todos los bloqueos juntos y ordenados evita deadlocks.
        """
        consulta = (
            select(InventarioRecurso)
            .where(
                or_(
                    and_(
                        InventarioRecurso.ong_id.in_(ong_ids),
                        InventarioRecurso.tipo_recurso_id.in_(tipo_ids),
                    ),
                    InventarioRecurso.id.in_(ademas),
                )
            )
            .order_by(InventarioRecurso.id)
        )
        return {fila.id: fila for fila in bloquear(consulta)}
