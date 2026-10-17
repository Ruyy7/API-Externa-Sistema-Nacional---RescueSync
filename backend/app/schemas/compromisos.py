from decimal import Decimal

from marshmallow import Schema, fields, validate

from app.models import EstadoCompromiso
from app.schemas import FiltrosSchema
from app.schemas.convocatorias import REFERENCIA, ConvocatoriaEntradaSchema, ConvocatoriaSchema

# Las cantidades son numeric(12,2) en la base
_MAXIMO = Decimal("9999999999.99")
CANTIDAD_POSITIVA = validate.Range(min=Decimal("0.01"), max=_MAXIMO)
CANTIDAD_NO_NEGATIVA = validate.Range(min=Decimal("0"), max=_MAXIMO)

_TIPO_RECURSO = {
    "description": "Código del catálogo de tipos de recurso (el mismo que usa la webapp).",
    "example": "PARAMEDICO",
}


# --- Entrada ---------------------------------------------------------------------------------


class ItemPedidoSchema(Schema):
    tipo_recurso = fields.Str(
        required=True, validate=validate.Length(min=1, max=40), metadata=_TIPO_RECURSO
    )
    cantidad = fields.Decimal(
        required=True, places=2, validate=CANTIDAD_POSITIVA, metadata={"example": 5}
    )


class ItemAdjudicadoSchema(Schema):
    tipo_recurso = fields.Str(
        required=True, validate=validate.Length(min=1, max=40), metadata=_TIPO_RECURSO
    )
    cantidad = fields.Decimal(
        required=True,
        places=2,
        validate=CANTIDAD_NO_NEGATIVA,
        metadata={
            "description": "Cantidad adjudicada; no puede superar la reservada.",
            "example": 3,
        },
    )


def _items(schema: type[Schema], descripcion: str) -> fields.List:
    return fields.List(
        fields.Nested(schema),
        required=True,
        validate=validate.Length(min=1, max=50),
        metadata={"description": descripcion},
    )


class VerificacionEntradaSchema(Schema):
    ong_cuit = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=13),
        metadata={
            "description": "CUIT de la ONG, tal como está registrada en el Sistema Nacional "
            "(el mismo identificador que usa POST /validaciones).",
            "example": "30-11111111-1",
        },
    )
    items = _items(ItemPedidoSchema, "Recursos y cantidades a verificar.")


class ReservaEntradaSchema(VerificacionEntradaSchema):
    oferta_referencia = fields.Str(
        required=True,
        validate=REFERENCIA,
        metadata={
            "description": "Id de la oferta en la webapp. Junto con la ONG identifica el "
            "compromiso: repetir el mismo pedido no reserva dos veces.",
            "example": "123",
        },
    )
    convocatoria = fields.Nested(
        ConvocatoriaEntradaSchema,
        required=True,
        metadata={
            "description": "Se registra la primera vez. Después sus fechas solo cambian con "
            "PUT /convocatorias/{referencia}."
        },
    )
    items = _items(ItemPedidoSchema, "Recursos que la ONG ofrece y quedan bloqueados.")


class AjusteEntradaSchema(Schema):
    items = _items(
        ItemPedidoSchema,
        "La reserva completa tal como queda: los tipos que no aparecen se liberan.",
    )


class ConfirmacionEntradaSchema(Schema):
    items = _items(
        ItemAdjudicadoSchema,
        "Cantidades adjudicadas. Los tipos reservados que no aparecen se adjudican en 0 y se "
        "liberan.",
    )


class CompromisoFiltrosSchema(FiltrosSchema):
    emergencia = fields.Str(metadata={"description": "Referencia de la emergencia en la webapp."})
    convocatoria = fields.Str(metadata={"description": "Referencia de la convocatoria."})
    ong_cuit = fields.Str()
    estado = fields.Str(validate=validate.OneOf(list(EstadoCompromiso)))
    oferta_referencia = fields.Str()


# --- Salida ----------------------------------------------------------------------------------


class TipoRecursoRefSchema(Schema):
    codigo = fields.Str()
    nombre = fields.Str()


class OngRefSchema(Schema):
    id = fields.Int()
    cuit = fields.Str()
    razon_social = fields.Str()


class ItemCompromisoSchema(Schema):
    tipo_recurso = fields.Nested(TipoRecursoRefSchema)
    cantidad_reservada = fields.Decimal(as_string=True)
    cantidad_comprometida = fields.Decimal(as_string=True)
    # Avance de la liberación (I-3.5)
    cantidad_liberada = fields.Decimal(as_string=True)
    cantidad_pendiente = fields.Decimal(
        as_string=True, metadata={"description": "Comprometido que sigue en ejecución."}
    )


class CompromisoSchema(Schema):
    id = fields.Int()
    oferta_referencia = fields.Str()
    ong = fields.Nested(OngRefSchema)
    convocatoria = fields.Nested(ConvocatoriaSchema)
    estado = fields.Str(metadata={"enum": list(EstadoCompromiso)})
    items = fields.List(fields.Nested(ItemCompromisoSchema))
    creado_por = fields.Str()
    creado_en = fields.DateTime()
    confirmado_en = fields.DateTime(allow_none=True)
    cancelado_en = fields.DateTime(allow_none=True)
    vencido_en = fields.DateTime(allow_none=True)
    finalizado_en = fields.DateTime(allow_none=True)


class ResultadoItemSchema(Schema):
    tipo_recurso = fields.Str()
    solicitado = fields.Decimal(as_string=True)
    disponible = fields.Decimal(as_string=True)
    resultado = fields.Str(metadata={"enum": ["DISPONIBLE", "PARCIAL", "SIN_DISPONIBILIDAD"]})


class VerificacionSchema(Schema):
    ong_cuit = fields.Str()
    ong_habilitada = fields.Bool()
    se_puede_reservar = fields.Bool()
    items = fields.List(fields.Nested(ResultadoItemSchema))


class ErrorUniformeSchema(Schema):
    """Formato uniforme de todos los errores de la API."""

    codigo = fields.Str(metadata={"example": "RECURSOS_INSUFICIENTES"})
    mensaje = fields.Str()
    detalles = fields.Dict()
