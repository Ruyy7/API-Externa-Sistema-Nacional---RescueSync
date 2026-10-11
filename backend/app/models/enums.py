"""Enumerados del dominio del Sistema Nacional."""

from enum import StrEnum


class EstadoONG(StrEnum):
    """El criterio de transición/habilitación se define en el punto de onboarding (I-3.1)."""

    PENDIENTE = "PENDIENTE"
    HABILITADA = "HABILITADA"
    SUSPENDIDA = "SUSPENDIDA"


class CategoriaRecurso(StrEnum):
    PERSONAL = "PERSONAL"
    MATERIAL = "MATERIAL"


class EstadoCompromiso(StrEnum):
    """Estado agregado del compromiso de una ONG para una oferta."""

    RESERVADO = "RESERVADO"
    COMPROMETIDO = "COMPROMETIDO"
    FINALIZADO = "FINALIZADO"
    CANCELADO = "CANCELADO"
    VENCIDO = "VENCIDO"
