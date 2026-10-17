from datetime import UTC

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

# Identificadores que vienen de la webapp (el id de la oferta o de la convocatoria). Van en la URL,
# así que no admiten barras ni espacios.
REFERENCIA = validate.Regexp(
    r"^[^/\s]{1,100}$", error="Hasta 100 caracteres, sin espacios ni barras."
)


class FechasConvocatoriaSchema(Schema):
    fecha_cierre = fields.AwareDateTime(
        required=True,
        default_timezone=UTC,
        metadata={"description": "Fin de la ventana de ofertas (el timer de la convocatoria)."},
    )
    fecha_limite_adjudicacion = fields.AwareDateTime(
        required=True,
        default_timezone=UTC,
        metadata={
            "description": "Fin de la ventana de adjudicación: ahí vencen las reservas no "
            "adjudicadas."
        },
    )

    @validates_schema
    def _limite_despues_del_cierre(self, datos, **_kwargs):
        if datos["fecha_limite_adjudicacion"] < datos["fecha_cierre"]:
            raise ValidationError(
                "No puede ser anterior a la fecha de cierre.", "fecha_limite_adjudicacion"
            )


class ConvocatoriaNuevaSchema(FechasConvocatoriaSchema):
    """Convocatoria que nace de una reformulación: hereda la emergencia de la original."""

    referencia = fields.Str(
        required=True,
        validate=REFERENCIA,
        metadata={"description": "Id de la convocatoria en la webapp.", "example": "45"},
    )


class ConvocatoriaEntradaSchema(ConvocatoriaNuevaSchema):
    emergencia_referencia = fields.Str(
        required=True,
        validate=REFERENCIA,
        metadata={
            "description": "Id de la emergencia en la webapp. La liberación (I-3.5) y Bonita "
            "ubican los compromisos por emergencia.",
            "example": "12",
        },
    )


class ReformulacionEntradaSchema(Schema):
    nueva = fields.Nested(
        ConvocatoriaNuevaSchema,
        required=True,
        metadata={
            "description": "Convocatoria que reemplaza a la reformulada. Pertenece a la misma "
            "emergencia, así que no hace falta repetirla."
        },
    )


class ConvocatoriaSchema(Schema):
    referencia = fields.Str()
    emergencia_referencia = fields.Str()
    fecha_cierre = fields.DateTime()
    fecha_limite_adjudicacion = fields.DateTime()


class ReformulacionSchema(Schema):
    convocatoria = fields.Nested(ConvocatoriaSchema)
    compromisos_movidos = fields.Int()
