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


def documentar_errores(bp: Blueprint, *codigos: int):
    def decorar(vista):
        for codigo in codigos:
            vista = bp.alt_response(
                codigo, schema=ErrorUniformeSchema, description=_DESCRIPCIONES[codigo]
            )(vista)
        return vista

    return decorar
