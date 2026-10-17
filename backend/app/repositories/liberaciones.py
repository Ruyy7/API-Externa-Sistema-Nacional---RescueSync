"""Consultas y bloqueos de la liberación y el cierre (I-3.5)."""

from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import select

from app.extensions import db
from app.models import (
    ONG,
    Actividad,
    CierreProyecto,
    Compromiso,
    CompromisoItem,
    Convocatoria,
    EstadoCompromiso,
    InventarioRecurso,
    TipoRecurso,
)
from app.repositories import paginar_entidades
from app.repositories.bloqueos import bloquear


@dataclass(frozen=True)
class ItemCandidato:
    """Ítem que podría recibir una actividad. Trae solo ids y estado a propósito: las entidades se
    cargan recién con el compromiso bloqueado, así ningún valor viejo queda en la sesión."""

    item_id: int
    compromiso_id: int
    oferta_referencia: str
    estado: EstadoCompromiso


class LiberacionRepository:
    def agregar(self, entidad: Actividad | CierreProyecto) -> None:
        db.session.add(entidad)

    # --- Actividades -----------------------------------------------------------------------

    def actividad_por_referencia(self, referencia: str) -> Actividad | None:
        return db.session.scalar(select(Actividad).where(Actividad.referencia == referencia))

    def obtener_actividad(self, actividad_id: int) -> Actividad | None:
        return db.session.get(Actividad, actividad_id)

    def candidatos(
        self,
        emergencia: str,
        ong_cuit: str,
        tipo_recurso: str,
        oferta_referencia: str | None = None,
    ) -> list[ItemCandidato]:
        """Ítems de esa ONG y categoría en la emergencia, en cualquier estado. No bloquea."""
        consulta = (
            select(
                CompromisoItem.id, Compromiso.id, Compromiso.oferta_referencia, Compromiso.estado
            )
            .select_from(CompromisoItem)
            .join(CompromisoItem.compromiso)
            .join(Compromiso.convocatoria)
            .join(Compromiso.ong)
            .join(CompromisoItem.inventario_recurso)
            .join(InventarioRecurso.tipo_recurso)
            .where(
                Convocatoria.emergencia_referencia == emergencia,
                ONG.cuit == ong_cuit,
                TipoRecurso.codigo == tipo_recurso,
            )
            .order_by(Compromiso.id)
        )
        if oferta_referencia is not None:
            consulta = consulta.where(Compromiso.oferta_referencia == oferta_referencia)
        return [ItemCandidato(*fila) for fila in db.session.execute(consulta)]

    def obtener_item(self, item_id: int) -> CompromisoItem | None:
        """Lee el ítem con los valores confirmados en la base, aunque ya estuviera en la sesión.
        Se llama con el compromiso bloqueado: nadie más puede estar cambiándolo."""
        consulta = (
            select(CompromisoItem)
            .where(CompromisoItem.id == item_id)
            .execution_options(populate_existing=True)
        )
        return db.session.scalar(consulta)

    def listar_actividades(
        self,
        pagina: int,
        tamano: int,
        *,
        emergencia: str | None = None,
        ong_cuit: str | None = None,
        tipo_recurso: str | None = None,
        origen: str | None = None,
        compromiso_id: int | None = None,
    ) -> tuple[list[Actividad], int]:
        consulta = (
            select(Actividad)
            .join(Actividad.item)
            .join(CompromisoItem.compromiso)
            .order_by(Actividad.id.desc())
        )
        if emergencia is not None:
            consulta = consulta.join(Compromiso.convocatoria).where(
                Convocatoria.emergencia_referencia == emergencia
            )
        if ong_cuit is not None:
            consulta = consulta.join(Compromiso.ong).where(ONG.cuit == ong_cuit)
        if tipo_recurso is not None:
            consulta = (
                consulta.join(CompromisoItem.inventario_recurso)
                .join(InventarioRecurso.tipo_recurso)
                .where(TipoRecurso.codigo == tipo_recurso)
            )
        if origen is not None:
            consulta = consulta.where(Actividad.origen == origen)
        if compromiso_id is not None:
            consulta = consulta.where(CompromisoItem.compromiso_id == compromiso_id)
        return paginar_entidades(consulta, pagina, tamano)

    # --- Emergencia ------------------------------------------------------------------------

    def existe_emergencia(self, emergencia: str) -> bool:
        """El Sistema Nacional conoce una emergencia cuando alguna convocatoria la nombra."""
        consulta = select(Convocatoria.id).where(Convocatoria.emergencia_referencia == emergencia)
        return db.session.scalar(consulta.limit(1)) is not None

    def compromisos_de_emergencia(
        self,
        emergencia: str,
        *,
        estados: Collection[EstadoCompromiso] | None = None,
        bloquear_filas: bool = False,
    ) -> list[Compromiso]:
        """Compromisos de la emergencia en orden de id; con bloquear_filas, SELECT ... FOR UPDATE.

        Filtra la convocatoria con una subconsulta y no con un JOIN: un FOR UPDATE con JOIN
        bloquearía también las filas de convocatoria, que I-3.4 modifica al reabrir o reformular.
        """
        convocatorias = select(Convocatoria.id).where(
            Convocatoria.emergencia_referencia == emergencia
        )
        consulta = (
            select(Compromiso)
            .where(Compromiso.convocatoria_id.in_(convocatorias))
            .order_by(Compromiso.id)
        )
        if estados is not None:
            consulta = consulta.where(Compromiso.estado.in_(estados))
        if bloquear_filas:
            return bloquear(consulta)
        return list(db.session.scalars(consulta))

    def cierre_de(self, emergencia: str) -> CierreProyecto | None:
        consulta = select(CierreProyecto).where(CierreProyecto.emergencia_referencia == emergencia)
        return db.session.scalar(consulta)
