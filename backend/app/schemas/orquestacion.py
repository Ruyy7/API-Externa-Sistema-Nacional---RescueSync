"""Contrato de las operaciones que invoca Bonita como orquestador
(docs/08-orquestacion-bonita.md).

Bonita reenvía el JSON que le entrega la webapp. Por eso la entrada es tolerante (Tolerant
Reader): los campos que la API no usa se ignoran en vez de fallar, y la webapp puede sumar datos
sin romper el conector.
"""

from datetime import UTC

from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates_schema

from app.schemas.compromisos import CompromisoSchema, ItemAdjudicadoSchema
from app.schemas.convocatorias import REFERENCIA
from app.schemas.liberaciones import ActividadEntradaSchema, ActividadSchema
from app.schemas.validaciones import OfertaPedidoSchema, ValidacionResultadoSchema


class _Tolerante(Schema):
    class Meta:
        unknown = EXCLUDE


# --- Validar ofertas: validación y bloqueo ---------------------------------------------------


class BloqueoPedidoSchema(_Tolerante):
    """El listado consolidado de ofertas que Bonita le pide a la webapp cuando vence la ventana
    [D-3], con las fechas de la convocatoria: los bloqueos vencen con su ventana de adjudicación."""

    convocatoria_referencia = fields.Str(
        required=True,
        validate=REFERENCIA,
        metadata={"description": "Id de la convocatoria en la webapp.", "example": "45"},
    )
    fecha_cierre = fields.AwareDateTime(
        required=True,
        default_timezone=UTC,
        metadata={"description": "Fin de la ventana de ofertas (el timer que acaba de vencer)."},
    )
    fecha_limite_adjudicacion = fields.AwareDateTime(
        required=True,
        default_timezone=UTC,
        metadata={
            "description": "Fin de la ventana de adjudicación: ahí vencen los bloqueos que no "
            "se adjudicaron."
        },
    )
    # Puede venir vacía: una convocatoria sin ofertas también pasa por *Validar ofertas*
    ofertas = fields.List(fields.Nested(OfertaPedidoSchema), required=True)

    @validates_schema
    def _limite_despues_del_cierre(self, datos, **_kwargs):
        if datos["fecha_limite_adjudicacion"] < datos["fecha_cierre"]:
            raise ValidationError(
                "No puede ser anterior a la fecha de cierre.", "fecha_limite_adjudicacion"
            )


class BloqueoResultadoSchema(ValidacionResultadoSchema):
    """El mismo resultado por línea de POST /validaciones: la webapp lo guarda tal cual."""

    emergencia_referencia = fields.Str()
    reservas = fields.Int(
        metadata={"description": "Cuántas ofertas por ONG quedaron con recursos bloqueados."}
    )


# --- Reabrir o reformular: liberar los bloqueos ------------------------------------------------


class DesbloqueoResultadoSchema(Schema):
    emergencia_referencia = fields.Str()
    reservas_canceladas = fields.Int(
        metadata={"description": "Bloqueos liberados. 0 si no quedaba ninguno (reintento)."}
    )


# --- Comprometer recursos ----------------------------------------------------------------------


class _ItemAdjudicadoSchema(ItemAdjudicadoSchema):
    class Meta:
        unknown = EXCLUDE


class AdjudicacionDeOfertaSchema(_Tolerante):
    oferta_referencia = fields.Str(required=True, validate=REFERENCIA)
    ong_cuit = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=13),
        metadata={"description": "ONG que aporta esos recursos (en un consorcio, cada una)."},
    )
    items = fields.List(
        fields.Nested(_ItemAdjudicadoSchema),
        required=True,
        metadata={"description": "Cantidad adjudicada por tipo de recurso. 0 = no se adjudica."},
    )


class AdjudicacionEntradaSchema(_Tolerante):
    """Lo que adjudicó el municipio, tal como Bonita se lo pide a la webapp."""

    convocatoria_referencia = fields.Str(required=True, validate=REFERENCIA)
    # Vacía = no se adjudicó nada: se liberan todos los bloqueos de la convocatoria
    adjudicaciones = fields.List(fields.Nested(AdjudicacionDeOfertaSchema), required=True)


class AdjudicacionResultadoSchema(Schema):
    emergencia_referencia = fields.Str()
    convocatoria_referencia = fields.Str()
    compromisos = fields.List(
        fields.Nested(CompromisoSchema),
        metadata={"description": "Los compromisos que quedaron COMPROMETIDO."},
    )
    reservas_canceladas = fields.Int(
        metadata={"description": "Bloqueos de ofertas no adjudicadas que se liberaron."}
    )


# --- Marcar actividad como finalizada ----------------------------------------------------------


class ActividadDeEmergenciaSchema(ActividadEntradaSchema):
    """Una actividad cumplida. La emergencia va en la URL."""

    class Meta:
        unknown = EXCLUDE
        exclude = ("emergencia_referencia",)


class ActividadesEntradaSchema(_Tolerante):
    # Vacía = no hay actividades nuevas que informar: no cambia nada
    actividades = fields.List(fields.Nested(ActividadDeEmergenciaSchema), required=True)


class ActividadesResultadoSchema(Schema):
    emergencia_referencia = fields.Str()
    nuevas = fields.Int(
        metadata={"description": "Actividades registradas por esta llamada (sin los reintentos)."}
    )
    actividades = fields.List(fields.Nested(ActividadSchema))
