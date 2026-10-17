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


class NivelCompetencia(StrEnum):
    """Resultado de validar una línea u oferta (I-3.3). No hay rechazo binario: NO_HABILITADO
    afecta solo a esa línea, y la oferta conserva el resto."""

    TOTAL = "TOTAL"
    PARCIAL = "PARCIAL"
    NO_HABILITADO = "NO_HABILITADO"


class MotivoNivel(StrEnum):
    """Por qué una línea no quedó con nivel TOTAL."""

    EXCEDE_DISPONIBLE = "EXCEDE_DISPONIBLE"
    SIN_DISPONIBILIDAD = "SIN_DISPONIBILIDAD"
    NO_INSCRIPTA = "NO_INSCRIPTA"
    ONG_NO_HABILITADA = "ONG_NO_HABILITADA"
    ONG_NO_REGISTRADA = "ONG_NO_REGISTRADA"


class RolSugerido(StrEnum):
    """Lugar de la línea en su lote [E-4]: cubrirlo entero o solo apoyar."""

    PRINCIPAL = "PRINCIPAL"
    APOYO = "APOYO"


class OrigenActividad(StrEnum):
    """Quién originó la liberación de una parte de un ítem comprometido (I-3.5)."""

    INFORMADA = "INFORMADA"  # la ONG informó una actividad cumplida
    CIERRE = "CIERRE"  # se liberó lo que quedaba al liberar los recursos de la emergencia


class AccionLiberacion(StrEnum):
    """Efecto de una liberación en el inventario (I-3.5). Se guarda en el historial porque
    `tipo_recurso.reutilizable` puede cambiar después y el historial no tiene que cambiar."""

    LIBERADO = "LIBERADO"  # reutilizable: vuelve al stock (comprometida -= n)
    CONSUMIDO = "CONSUMIDO"  # consumible: sale del stock (comprometida -= n y total -= n)
