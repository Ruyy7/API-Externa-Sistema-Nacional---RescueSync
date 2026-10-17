"""Contrato HTTP de la liberación y el cierre (I-3.5). Las cantidades son numeric(12,2)."""

from datetime import UTC

from marshmallow import Schema, fields, validate

from app.models import AccionLiberacion, EstadoCompromiso, OrigenActividad
from app.schemas import FiltrosSchema
from app.schemas.compromisos import CANTIDAD_POSITIVA, OngRefSchema, TipoRecursoRefSchema
from app.schemas.convocatorias import REFERENCIA

# --- Entrada ---------------------------------------------------------------------------------


class ActividadEntradaSchema(Schema):
    """Lo que informa la webapp cuando la ONG marca una actividad como finalizada [E-7]: "para esta
    emergencia, para esta ONG, para esta categoría y estos recursos, se cumplió la tarea en tal
    fecha y con tales observaciones" (respuesta del docente)."""

    actividad_referencia = fields.Str(
        required=True,
        validate=REFERENCIA,
        metadata={
            "description": "Id de la actividad en la webapp. Repetir el mismo pedido no libera "
            "dos veces: responde la actividad ya registrada.",
            "example": "ACT-88",
        },
    )
    emergencia_referencia = fields.Str(
        required=True,
        validate=REFERENCIA,
        metadata={
            "description": "Id de la emergencia en la webapp (`emergenciaId` en Bonita).",
            "example": "12",
        },
    )
    ong_cuit = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=13),
        metadata={
            "description": "CUIT de la ONG que cumplió la actividad, como en el resto de la API.",
            "example": "30-11111111-1",
        },
    )
    tipo_recurso = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=40),
        metadata={
            "description": "La categoría: código del catálogo compartido con la webapp.",
            "example": "PARAMEDICO",
        },
    )
    cantidad = fields.Decimal(
        required=True,
        places=2,
        validate=CANTIDAD_POSITIVA,
        metadata={
            "description": "Recursos de esa categoría que terminaron su tarea. No puede superar "
            "lo comprometido que falta liberar.",
            "example": 3,
        },
    )
    fecha = fields.AwareDateTime(
        required=True,
        default_timezone=UTC,
        metadata={
            "description": "Cuándo se cumplió la tarea (ISO-8601; sin zona horaria se toma como "
            "UTC). No puede ser futura.",
            "example": "2026-10-20T15:30:00-03:00",
        },
    )
    observaciones = fields.Str(
        load_default=None, allow_none=True, validate=validate.Length(max=2000)
    )
    oferta_referencia = fields.Str(
        load_default=None,
        allow_none=True,
        validate=REFERENCIA,
        metadata={
            "description": "Solo hace falta si la ONG tiene más de un compromiso con esa "
            "categoría en la emergencia (por ejemplo, una oferta propia y un consorcio).",
            "example": "OF-15",
        },
    )


class ActividadFiltrosSchema(FiltrosSchema):
    emergencia = fields.Str(metadata={"description": "Referencia de la emergencia en la webapp."})
    ong_cuit = fields.Str()
    tipo_recurso = fields.Str(metadata={"description": "Código del tipo de recurso."})
    origen = fields.Str(validate=validate.OneOf(list(OrigenActividad)))
    compromiso_id = fields.Int()


# --- Salida ----------------------------------------------------------------------------------


class ItemLiberacionSchema(Schema):
    tipo_recurso = fields.Nested(TipoRecursoRefSchema)
    cantidad_comprometida = fields.Decimal(as_string=True)
    cantidad_liberada = fields.Decimal(as_string=True)
    cantidad_pendiente = fields.Decimal(
        as_string=True, metadata={"description": "Comprometido que sigue en ejecución."}
    )


class ActividadSchema(Schema):
    id = fields.Int()
    actividad_referencia = fields.Str(attribute="referencia", allow_none=True)
    origen = fields.Str(metadata={"enum": list(OrigenActividad)})
    accion = fields.Str(
        metadata={
            "enum": list(AccionLiberacion),
            "description": "LIBERADO: volvió al stock. CONSUMIDO: se dio de baja del stock.",
        }
    )
    emergencia_referencia = fields.Str(
        attribute="item.compromiso.convocatoria.emergencia_referencia"
    )
    oferta_referencia = fields.Str(attribute="item.compromiso.oferta_referencia")
    compromiso_id = fields.Int(attribute="item.compromiso_id")
    estado_compromiso = fields.Str(
        attribute="item.compromiso.estado", metadata={"enum": list(EstadoCompromiso)}
    )
    ong = fields.Nested(OngRefSchema, attribute="item.compromiso.ong")
    tipo_recurso = fields.Nested(TipoRecursoRefSchema, attribute="item.tipo_recurso")
    cantidad = fields.Decimal(as_string=True)
    fecha = fields.DateTime(attribute="fecha_cumplimiento")
    observaciones = fields.Str(allow_none=True)
    registrada_por = fields.Str()
    creado_en = fields.DateTime()
    item = fields.Nested(
        ItemLiberacionSchema, metadata={"description": "Cómo queda el ítem después de esta."}
    )


# --- Liberación y cierre de la emergencia ----------------------------------------------------


class CierreEntradaSchema(Schema):
    """Cuerpo de la liberación y del cierre de la emergencia. Los dispara el sistema (Bonita o la
    webapp), así que la fecha es opcional: si no viene, es el momento de la llamada."""

    fecha = fields.AwareDateTime(
        load_default=None,
        allow_none=True,
        default_timezone=UTC,
        metadata={
            "description": "Cuándo ocurrió (ISO-8601; sin zona horaria se toma como UTC). No "
            "puede ser futura. Si falta, es ahora.",
            "example": "2026-10-25T18:00:00-03:00",
        },
    )
    observaciones = fields.Str(
        load_default=None, allow_none=True, validate=validate.Length(max=2000)
    )


class CierreProyectoSchema(Schema):
    emergencia_referencia = fields.Str()
    fecha_cierre = fields.DateTime()
    observaciones = fields.Str(allow_none=True)
    cerrado_por = fields.Str()
    creado_en = fields.DateTime()


class CompromisoLiberacionSchema(Schema):
    id = fields.Int()
    oferta_referencia = fields.Str()
    ong = fields.Nested(OngRefSchema)
    estado = fields.Str(metadata={"enum": list(EstadoCompromiso)})
    finalizado_en = fields.DateTime(allow_none=True)
    items = fields.List(fields.Nested(ItemLiberacionSchema))


class EstadoEmergenciaSchema(Schema):
    emergencia_referencia = fields.Str()
    todo_liberado = fields.Bool(
        metadata={
            "description": "No queda nada comprometido en ejecución. Es lo que Bonita necesita "
            "para *Finalizaron todas las tareas?*."
        }
    )
    cerrado = fields.Bool()
    cierre = fields.Nested(CierreProyectoSchema, allow_none=True)
    reservas_vigentes = fields.Int(
        metadata={
            "description": "Reservas sin adjudicar que siguen RESERVADO. La liberación no las "
            "toca: vencen por fecha (I-3.4)."
        }
    )
    compromisos = fields.List(fields.Nested(CompromisoLiberacionSchema))


class LiberacionEmergenciaSchema(EstadoEmergenciaSchema):
    liberaciones = fields.List(
        fields.Nested(ActividadSchema),
        metadata={
            "description": "Lo que liberó esta llamada, con origen CIERRE. Vacío si no quedaba "
            "nada pendiente."
        },
    )
