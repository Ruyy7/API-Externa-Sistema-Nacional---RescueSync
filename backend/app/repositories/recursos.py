from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select

from app.extensions import db
from app.models import (
    ONG,
    Compromiso,
    CompromisoItem,
    EstadoCompromiso,
    EstadoONG,
    InventarioRecurso,
    TipoRecurso,
)
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

    def codigos_existentes(self, codigos: set[str]) -> set[str]:
        consulta = select(TipoRecurso.codigo).where(TipoRecurso.codigo.in_(codigos))
        return set(db.session.scalars(consulta))

    def disponible_por_ong_y_tipo(
        self, cuits: set[str], codigos: set[str]
    ) -> dict[tuple[str, str], Decimal]:
        """Disponible (total - bloqueada - comprometida) por (CUIT, código de tipo).

        Que exista la fila significa que la ONG está inscripta en esa categoría.
        """
        consulta = (
            select(
                ONG.cuit,
                TipoRecurso.codigo,
                InventarioRecurso.cantidad_total
                - InventarioRecurso.cantidad_bloqueada
                - InventarioRecurso.cantidad_comprometida,
            )
            .select_from(InventarioRecurso)
            .join(InventarioRecurso.ong)
            .join(InventarioRecurso.tipo_recurso)
            .where(ONG.cuit.in_(cuits), TipoRecurso.codigo.in_(codigos))
        )
        return {
            (cuit, codigo): disponible for cuit, codigo, disponible in db.session.execute(consulta)
        }

    def reservado_por_ofertas(self, ofertas: set[str]) -> dict[tuple[str, str, str], Decimal]:
        """Lo que cada oferta ya tiene reservado, por (oferta, CUIT, código de tipo).

        Sirve para que una oferta no compita contra su propia reserva al revalidarse.
        """
        consulta = (
            select(
                Compromiso.oferta_referencia,
                ONG.cuit,
                TipoRecurso.codigo,
                CompromisoItem.cantidad_reservada,
            )
            .select_from(CompromisoItem)
            .join(CompromisoItem.compromiso)
            .join(Compromiso.ong)
            .join(CompromisoItem.inventario_recurso)
            .join(InventarioRecurso.tipo_recurso)
            .where(
                Compromiso.oferta_referencia.in_(ofertas),
                Compromiso.estado == EstadoCompromiso.RESERVADO,
            )
        )
        return {
            (oferta, cuit, codigo): reservado
            for oferta, cuit, codigo, reservado in db.session.execute(consulta)
        }

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
