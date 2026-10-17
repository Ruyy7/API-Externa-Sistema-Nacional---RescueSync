"""Validación por niveles de competencia (I-3.3).

Evalúa las ofertas de una convocatoria contra lo que cada ONG declaró al registrarse (una fila de
`inventario_recurso` por categoría, con su máximo) y lo que ya tiene reservado o comprometido.
No rechaza ofertas enteras: cada línea se acepta total o parcialmente, o queda sin habilitar.
Solo lee: el bloqueo y el compromiso son del punto I-3.4 (docs/03-validacion-por-competencia.md).
"""

import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal

from app.errors import ReglaDeNegocio
from app.models import MotivoNivel, NivelCompetencia, RolSugerido
from app.repositories.ongs import ONGRepository
from app.repositories.recursos import RecursoRepository

log = logging.getLogger(__name__)
CERO = Decimal("0")


@dataclass(frozen=True)
class Evaluacion:
    cantidad_habilitada: Decimal
    cantidad_aceptada: Decimal
    nivel: NivelCompetencia
    motivo: MotivoNivel | None
    rol_sugerido: RolSugerido | None


def evaluar_linea(
    ofrecida: Decimal,
    requerida: Decimal,
    habilitada: Decimal,
    impedimento: MotivoNivel | None = None,
) -> Evaluacion:
    """Clasifica una línea. Es una función pura: no conoce la base.

    `habilitada` es lo que la ONG todavía puede aportar en esa categoría. Un `impedimento`
    (ONG no habilitada, no inscripta, etc.) la deja en cero.
    """
    if impedimento:
        habilitada = CERO
    aceptada = min(ofrecida, habilitada)

    if aceptada == ofrecida:
        nivel, motivo = NivelCompetencia.TOTAL, None
    elif aceptada > 0:
        nivel, motivo = NivelCompetencia.PARCIAL, MotivoNivel.EXCEDE_DISPONIBLE
    else:
        nivel, motivo = (
            NivelCompetencia.NO_HABILITADO,
            impedimento or MotivoNivel.SIN_DISPONIBILIDAD,
        )

    if aceptada >= requerida:
        rol = RolSugerido.PRINCIPAL
    elif aceptada > 0:
        rol = RolSugerido.APOYO
    else:
        rol = None
    return Evaluacion(habilitada, aceptada, nivel, motivo, rol)


def nivel_de_oferta(niveles: list[NivelCompetencia]) -> NivelCompetencia:
    """TOTAL si todas las líneas lo son, NO_HABILITADO si ninguna aportó nada; si no, PARCIAL."""
    if all(n == NivelCompetencia.TOTAL for n in niveles):
        return NivelCompetencia.TOTAL
    if all(n == NivelCompetencia.NO_HABILITADO for n in niveles):
        return NivelCompetencia.NO_HABILITADO
    return NivelCompetencia.PARCIAL


class ValidacionService:
    """Service Layer del caso de uso "validar ofertas de una convocatoria"."""

    def __init__(self, recursos: RecursoRepository, ongs: ONGRepository):
        self.recursos = recursos
        self.ongs = ongs

    def validar(self, pedido: dict) -> dict:
        items = [item for oferta in pedido["ofertas"] for item in oferta["items"]]
        cuits = {item["ong_cuit"] for item in items}
        codigos = {item["tipo_recurso"] for item in items}

        desconocidos = sorted(codigos - self.recursos.codigos_existentes(codigos))
        if desconocidos:
            # Es un error de integración (catálogo desalineado), no de la ONG: falla todo el pedido.
            raise ReglaDeNegocio(
                "Hay tipos de recurso que no existen en el catálogo nacional.",
                codigo="TIPO_RECURSO_DESCONOCIDO",
                detalles={"tipos_recurso": desconocidos},
            )

        ongs = self.ongs.por_cuits(cuits)
        disponible = self.recursos.disponible_por_ong_y_tipo(cuits, codigos)
        reservado = self.recursos.reservado_por_ofertas(
            {oferta["oferta_referencia"] for oferta in pedido["ofertas"]}
        )
        ofertas = [
            self._evaluar_oferta(oferta, ongs, disponible, reservado)
            for oferta in pedido["ofertas"]
        ]
        log.info(
            "Ofertas validadas",
            extra={
                "contexto": {
                    "convocatoria": pedido["convocatoria_referencia"],
                    "niveles": {o["oferta_referencia"]: str(o["nivel"]) for o in ofertas},
                }
            },
        )
        return {"convocatoria_referencia": pedido["convocatoria_referencia"], "ofertas": ofertas}

    @staticmethod
    def _evaluar_oferta(oferta: dict, ongs: dict, disponible: dict, reservado: dict) -> dict:
        # Cada oferta se evalúa por separado: son alternativas que el municipio elige [E-5].
        # Dentro de una oferta, las líneas de la misma ONG y categoría comparten lo disponible.
        usado: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        items = []
        for item in oferta["items"]:
            clave = (item["ong_cuit"], item["tipo_recurso"])
            ong = ongs.get(item["ong_cuit"])
            if ong is None:
                impedimento = MotivoNivel.ONG_NO_REGISTRADA
            elif not ong.habilitada:
                impedimento = MotivoNivel.ONG_NO_HABILITADA
            elif clave not in disponible:
                impedimento = MotivoNivel.NO_INSCRIPTA
            else:
                impedimento = None

            habilitada = CERO
            if impedimento is None:
                propio = reservado.get((oferta["oferta_referencia"], *clave), CERO)
                habilitada = disponible[clave] + propio - usado[clave]

            evaluacion = evaluar_linea(
                item["cantidad_ofrecida"], item["cantidad_requerida"], habilitada, impedimento
            )
            usado[clave] += evaluacion.cantidad_aceptada
            items.append({**item, **asdict(evaluacion)})

        return {
            "oferta_referencia": oferta["oferta_referencia"],
            "nivel": nivel_de_oferta([item["nivel"] for item in items]),
            "items": items,
        }
