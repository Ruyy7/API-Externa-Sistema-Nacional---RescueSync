"""Cambios de las convocatorias que afectan el vencimiento de las reservas (I-3.4).

Las reservas vencen al terminar la ventana de adjudicación de su convocatoria. Por eso reabrir
una convocatoria (fechas nuevas) o reformularla (convocatoria nueva) mueve su vencimiento. Lo que
ya venció con las fechas anteriores sigue vencido.
"""

import logging

from app.errors import NoEncontrado, ReglaDeNegocio
from app.extensions import db
from app.models import Convocatoria
from app.repositories.bloqueos import iniciar_transaccion_con_bloqueos
from app.repositories.compromisos import CompromisoRepository, ConvocatoriaRepository
from app.services.compromisos import CompromisoService

log = logging.getLogger(__name__)


class ConvocatoriaService:
    def __init__(
        self,
        convocatorias: ConvocatoriaRepository,
        compromisos: CompromisoRepository,
        servicio_de_compromisos: CompromisoService,
        *,
        lock_timeout_ms: int,
    ):
        self.convocatorias = convocatorias
        self.compromisos = compromisos
        self.servicio_de_compromisos = servicio_de_compromisos
        self.lock_timeout_ms = lock_timeout_ms

    def obtener(self, referencia: str) -> Convocatoria:
        convocatoria = self.convocatorias.por_referencia(referencia)
        if convocatoria is None:
            raise NoEncontrado("La convocatoria no existe.")
        return convocatoria

    def actualizar_fechas(self, referencia: str, datos: dict) -> Convocatoria:
        """Reabrir: las reservas vigentes pasan a vencer con las fechas nuevas."""
        convocatoria = self.obtener(referencia)
        self.servicio_de_compromisos.vencer_atrasados(convocatoria_id=convocatoria.id)
        convocatoria = self.obtener(referencia)
        convocatoria.fecha_cierre = datos["fecha_cierre"]
        convocatoria.fecha_limite_adjudicacion = datos["fecha_limite_adjudicacion"]
        db.session.commit()
        log.info("Fechas de convocatoria actualizadas", extra={"contexto": {"ref": referencia}})
        return convocatoria

    def reformular(self, referencia: str, datos: dict) -> tuple[Convocatoria, int]:
        """Reformular: las reservas vigentes pasan a la convocatoria nueva y vencen con ella.

        Es idempotente: si se repite, la convocatoria nueva ya existe y no queda nada por mover.
        """
        origen = self.obtener(referencia)
        if datos["referencia"] == referencia:
            raise ReglaDeNegocio(
                "La convocatoria nueva tiene que tener otra referencia.",
                detalles={"json": {"nueva": {"referencia": ["Es igual a la original."]}}},
            )
        self.servicio_de_compromisos.vencer_atrasados(convocatoria_id=origen.id)
        destino = self.convocatorias.asegurar(
            datos["referencia"],
            origen.emergencia_referencia,
            datos["fecha_cierre"],
            datos["fecha_limite_adjudicacion"],
        )
        origen_id, destino_id = origen.id, destino.id
        iniciar_transaccion_con_bloqueos(self.lock_timeout_ms)
        movidos = self.compromisos.mover_reservados(origen_id, destino_id)
        db.session.commit()
        contexto = {"origen": referencia, "destino": datos["referencia"], "movidos": movidos}
        log.info("Convocatoria reformulada", extra={"contexto": contexto})
        return self.obtener(datos["referencia"]), movidos
