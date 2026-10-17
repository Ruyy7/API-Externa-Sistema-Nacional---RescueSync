"""Documentación en Swagger de las respuestas de error, todas con el formato uniforme."""

from flask_smorest import Blueprint

from app.schemas.compromisos import ErrorUniformeSchema

_DESCRIPCIONES = {
    401: "Falta el token o no es válido.",
    403: "El rol del token no permite la operación.",
    404: "No existe.",
    409: "Choca con el estado actual: recursos insuficientes, ventana cerrada, reserva vencida, "
    "recurso ocupado (reintentar) o transición inválida.",
    422: "Datos inválidos: ONG inexistente o no habilitada, tipo de recurso desconocido o "
    "cantidad no válida.",
}


def documentar_errores(bp: Blueprint, *codigos: int, descripciones: dict[int, str] | None = None):
    """Documenta los errores con su descripción general; `descripciones` la reemplaza por código
    para un blueprint con sus propios casos (por ejemplo, la liberación de I-3.5)."""
    textos = {**_DESCRIPCIONES, **(descripciones or {})}

    def decorar(vista):
        for codigo in codigos:
            vista = bp.alt_response(codigo, schema=ErrorUniformeSchema, description=textos[codigo])(
                vista
            )
        return vista

    return decorar
