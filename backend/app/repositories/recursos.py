from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select

from app.extensions import db
from app.models import EstadoONG, InventarioRecurso, ONG, TipoRecurso
from app.repositories import paginar, paginar_entidades


@dataclass(frozen=True)
class DisponibilidadGlobal:
    tipo_recurso: TipoRecurso
    cantidad_total: Decimal
    cantidad_bloqueada: Decimal
    cantidad_comprometida: Decimal
    cantidad_disponible: Decimal


class RecursoRepository:
    def tipos(
        self, pagina: int, tamano: int, *, solo_activos: bool = True
    ) -> tuple[list[TipoRecurso], int]:
        consulta = select(TipoRecurso).order_by(TipoRecurso.nombre)
        if solo_activos:
            consulta = consulta.where(TipoRecurso.activo)
        return paginar_entidades(consulta, pagina, tamano)

    def inventario_de_ong(self, ong_id: int) -> list[InventarioRecurso]:
        consulta = (
            select(InventarioRecurso)
            .where(InventarioRecurso.ong_id == ong_id)
            .join(InventarioRecurso.tipo_recurso)
            .order_by(TipoRecurso.nombre)
        )
        return list(db.session.scalars(consulta))

    def disponibilidad_global(
        self,
        pagina: int,
        tamano: int,
        *,
        tipo_recurso_id: int | None = None,
        ong_id: int | None = None,
        solo_ongs_habilitadas: bool = True,
    ) -> tuple[list[DisponibilidadGlobal], int]:
        total = func.sum(InventarioRecurso.cantidad_total).label("cantidad_total")
        bloqueada = func.sum(InventarioRecurso.cantidad_bloqueada).label("cantidad_bloqueada")
        comprometida = func.sum(InventarioRecurso.cantidad_comprometida).label(
            "cantidad_comprometida"
        )
        consulta = (
            select(TipoRecurso, total, bloqueada, comprometida)
            .join(InventarioRecurso, InventarioRecurso.tipo_recurso_id == TipoRecurso.id)
            .join(ONG, ONG.id == InventarioRecurso.ong_id)
            .where(TipoRecurso.activo)
            .group_by(TipoRecurso.id)
            .order_by(TipoRecurso.nombre)
        )
        if solo_ongs_habilitadas:
            consulta = consulta.where(ONG.estado == EstadoONG.HABILITADA)
        if tipo_recurso_id is not None:
            consulta = consulta.where(TipoRecurso.id == tipo_recurso_id)
        if ong_id is not None:
            consulta = consulta.where(ONG.id == ong_id)

        filas, cantidad = paginar(consulta, pagina, tamano)
        resultado = [
            DisponibilidadGlobal(
                tipo_recurso=tipo,
                cantidad_total=cantidad_total,
                cantidad_bloqueada=cantidad_bloqueada,
                cantidad_comprometida=cantidad_comprometida,
                cantidad_disponible=cantidad_total - cantidad_bloqueada - cantidad_comprometida,
            )
            for tipo, cantidad_total, cantidad_bloqueada, cantidad_comprometida in filas
        ]
        return resultado, cantidad
