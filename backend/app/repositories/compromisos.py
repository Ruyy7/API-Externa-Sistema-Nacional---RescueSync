from collections.abc import Collection
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.extensions import db
from app.models import ONG, Compromiso, CompromisoItem, Convocatoria, EstadoCompromiso
from app.repositories import paginar_entidades
from app.repositories.bloqueos import bloquear, esperando_bloqueos


class ConvocatoriaRepository:
    def por_referencia(self, referencia: str) -> Convocatoria | None:
        return db.session.scalar(select(Convocatoria).where(Convocatoria.referencia == referencia))

    def asegurar(
        self,
        referencia: str,
        emergencia_referencia: str,
        fecha_cierre: datetime,
        fecha_limite_adjudicacion: datetime,
    ) -> Convocatoria:
        """Crea la convocatoria si todavía no existe y la devuelve.

        INSERT ... ON CONFLICT DO NOTHING evita que dos reservas simultáneas de la misma
        convocatoria choquen con el UNIQUE de la referencia.
        """
        insercion = (
            insert(Convocatoria)
            .values(
                referencia=referencia,
                emergencia_referencia=emergencia_referencia,
                fecha_cierre=fecha_cierre,
                fecha_limite_adjudicacion=fecha_limite_adjudicacion,
            )
            .on_conflict_do_nothing(index_elements=["referencia"])
        )
        db.session.execute(insercion)
        return self.por_referencia(referencia)


class CompromisoRepository:
    def agregar(self, compromiso: Compromiso) -> None:
        db.session.add(compromiso)

    def obtener(
        self, compromiso_id: int, *, bloquear_fila: bool = False, saltear_ocupado: bool = False
    ) -> Compromiso | None:
        """Con bloquear_fila, toma el bloqueo del compromiso hasta el fin de la transacción.

        saltear_ocupado devuelve None si otra operación lo tiene bloqueado (SKIP LOCKED).
        """
        consulta = select(Compromiso).where(Compromiso.id == compromiso_id)
        if not bloquear_fila:
            return db.session.scalar(consulta)
        filas = bloquear(consulta, saltear_ocupadas=saltear_ocupado)
        return filas[0] if filas else None

    def por_oferta_y_ong(self, oferta_referencia: str, ong_id: int) -> Compromiso | None:
        consulta = select(Compromiso).where(
            Compromiso.oferta_referencia == oferta_referencia, Compromiso.ong_id == ong_id
        )
        return db.session.scalar(consulta)

    def ids_vencidos(
        self,
        momento: datetime,
        *,
        inventario_ids: Collection[int] | None = None,
        convocatoria_id: int | None = None,
    ) -> list[int]:
        """Reservas cuya ventana de adjudicación terminó y todavía no se vencieron."""
        consulta = (
            select(Compromiso.id)
            .join(Compromiso.convocatoria)
            .where(
                Compromiso.estado == EstadoCompromiso.RESERVADO,
                Convocatoria.fecha_limite_adjudicacion <= momento,
            )
            .order_by(Compromiso.id)
        )
        if inventario_ids is not None:
            consulta = consulta.where(
                Compromiso.items.any(CompromisoItem.inventario_recurso_id.in_(inventario_ids))
            )
        if convocatoria_id is not None:
            consulta = consulta.where(Compromiso.convocatoria_id == convocatoria_id)
        return list(db.session.scalars(consulta))

    def mover_reservados(self, origen_id: int, destino_id: int) -> int:
        """Pasa las reservas vigentes de una convocatoria a otra. Devuelve cuántas movió."""
        sentencia = (
            update(Compromiso)
            .where(
                Compromiso.convocatoria_id == origen_id,
                Compromiso.estado == EstadoCompromiso.RESERVADO,
            )
            .values(convocatoria_id=destino_id)
            .execution_options(synchronize_session=False)
        )
        with esperando_bloqueos():
            return db.session.execute(sentencia).rowcount

    def listar(
        self,
        pagina: int,
        tamano: int,
        *,
        emergencia: str | None = None,
        convocatoria: str | None = None,
        ong_cuit: str | None = None,
        estado: str | None = None,
        oferta_referencia: str | None = None,
    ) -> tuple[list[Compromiso], int]:
        consulta = select(Compromiso).order_by(Compromiso.id.desc())
        if emergencia is not None or convocatoria is not None:
            consulta = consulta.join(Compromiso.convocatoria)
        if emergencia is not None:
            consulta = consulta.where(Convocatoria.emergencia_referencia == emergencia)
        if convocatoria is not None:
            consulta = consulta.where(Convocatoria.referencia == convocatoria)
        if ong_cuit is not None:
            consulta = consulta.join(Compromiso.ong).where(ONG.cuit == ong_cuit)
        if estado is not None:
            consulta = consulta.where(Compromiso.estado == estado)
        if oferta_referencia is not None:
            consulta = consulta.where(Compromiso.oferta_referencia == oferta_referencia)
        return paginar_entidades(consulta, pagina, tamano)
