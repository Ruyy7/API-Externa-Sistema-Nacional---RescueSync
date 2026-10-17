"""Casos de uso de I-3.5: actividades cumplidas, liberación de recursos y cierre del proyecto.

Flujo (respuestas del docente y [E-7]):
- Cuando la ONG marca una actividad como finalizada, la webapp la informa acá: "para esta
  emergencia, para esta ONG, para esta categoría y estos recursos, se cumplió la tarea en tal fecha
  y con tales observaciones". Se libera a medida que termina cada actividad: lo reutilizable vuelve
  al stock y lo consumible se da de baja.
- Cuando no queda nada pendiente, el compromiso pasa a FINALIZADO.
- Bonita libera lo que quede (*Liberar recursos*) y cierra el proyecto (*Cerrar proyecto*).

Cada escritura corre en una transacción con el mismo orden de bloqueo que I-3.4: primero el
compromiso y después las filas de inventario, en orden de id (app/repositories/bloqueos.py).
Nunca toca cantidad_bloqueada ni cantidad_reservada: las reservas son del punto 4.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.errors import Conflicto, NoEncontrado, ReglaDeNegocio, TransicionInvalida
from app.extensions import db
from app.models import (
    ONG,
    AccionLiberacion,
    Actividad,
    CierreProyecto,
    Compromiso,
    CompromisoItem,
    EstadoCompromiso,
    InventarioRecurso,
    OrigenActividad,
)
from app.models.comun import ahora
from app.repositories.bloqueos import iniciar_transaccion_con_bloqueos
from app.repositories.compromisos import CompromisoRepository
from app.repositories.inventario import InventarioRepository
from app.repositories.liberaciones import ItemCandidato, LiberacionRepository
from app.repositories.ongs import ONGRepository

log = logging.getLogger(__name__)

# Diferencia de reloj tolerada entre el cliente y la API para "la tarea se cumplió ahora"
TOLERANCIA_DE_RELOJ = timedelta(minutes=5)


def aplicar_en_inventario(inventario: InventarioRecurso, cantidad: Decimal) -> AccionLiberacion:
    """Lo reutilizable vuelve al stock; lo consumible se da de baja (docs/02).

    Se llama con la fila ya bloqueada. Devuelve qué pasó, para guardarlo en el historial.
    """
    if inventario.tipo_recurso.reutilizable:
        inventario.liberar(cantidad)
        return AccionLiberacion.LIBERADO
    inventario.consumir(cantidad)
    return AccionLiberacion.CONSUMIDO


def es_fecha_futura(fecha: datetime, momento: datetime) -> bool:
    return fecha > momento + TOLERANCIA_DE_RELOJ


class LiberacionService:
    def __init__(
        self,
        liberaciones: LiberacionRepository,
        compromisos: CompromisoRepository,
        inventario: InventarioRepository,
        ongs: ONGRepository,
        *,
        lock_timeout_ms: int,
    ):
        self.liberaciones = liberaciones
        self.compromisos = compromisos
        self.inventario = inventario
        self.ongs = ongs
        self.lock_timeout_ms = lock_timeout_ms

    # --- Actividades cumplidas -----------------------------------------------------------------

    def registrar_actividad(self, datos: dict, autor: str) -> tuple[Actividad, bool]:
        """Registra la actividad y libera su cantidad del ítem comprometido. Devuelve
        (actividad, es_nueva).

        Es idempotente por `actividad_referencia`: si la webapp reintenta el mismo pedido, recibe
        la actividad ya registrada en lugar de liberar dos veces.
        """
        self._validar(datos)
        if (previa := self._previa(datos)) is not None:
            return previa, False
        self._exigir_proyecto_abierto(datos["emergencia_referencia"])
        candidato = self._resolver_candidato(datos)

        self._iniciar_transaccion()
        compromiso = self._compromiso_bloqueado(candidato.compromiso_id)
        # Un reintento simultáneo pudo registrarla mientras esperábamos el bloqueo
        if (previa := self._previa(datos)) is not None:
            db.session.commit()
            return previa, False
        self._exigir_comprometido(compromiso)
        # Recién ahora se cargan el ítem y el inventario: con el compromiso bloqueado, los valores
        # que se leen son los últimos confirmados y nadie puede cambiarlos hasta el commit.
        item = self.liberaciones.obtener_item(candidato.item_id)
        inventario = self.inventario.bloquear_por_ids([item.inventario_recurso_id])[
            item.inventario_recurso_id
        ]
        self._exigir_pendiente(item, datos["cantidad"])

        actividad = self._liberar(
            item,
            inventario,
            datos["cantidad"],
            origen=OrigenActividad.INFORMADA,
            referencia=datos["actividad_referencia"],
            fecha=datos["fecha"],
            observaciones=datos.get("observaciones"),
            autor=autor,
        )
        if compromiso.todo_liberado():
            compromiso.transicionar(EstadoCompromiso.FINALIZADO)
        db.session.commit()
        self._registrar("Actividad registrada", actividad)
        return actividad, True

    # --- Liberación y cierre de la emergencia --------------------------------------------------

    def estado_de_emergencia(self, emergencia: str) -> dict:
        """Qué queda por liberar en la emergencia. Bonita lo consulta desde *Monitorear recursos*
        para decidir *Finalizaron todas las tareas?*; el coordinador y el auditor, para seguir el
        despliegue."""
        self._exigir_emergencia(emergencia)
        return self._estado(emergencia)

    def liberar_emergencia(self, emergencia: str, datos: dict, autor: str) -> dict:
        """*Liberar recursos*: libera lo que siga comprometido en la emergencia y finaliza esos
        compromisos. Lo que la ONG no informó se libera igual, con origen CIERRE.

        Es idempotente: si no queda nada pendiente, no cambia nada. Las reservas sin adjudicar no
        se tocan (son del punto 4 y vencen por fecha); se informan en `reservas_vigentes`.
        """
        self._exigir_emergencia(emergencia)
        fecha = self._fecha_o_ahora(datos)
        self._exigir_proyecto_abierto(emergencia)

        self._iniciar_transaccion()
        # Mismo orden que I-3.4: primero los compromisos (por id) y después el inventario (por id)
        comprometidos = self.liberaciones.compromisos_de_emergencia(
            emergencia, estados=[EstadoCompromiso.COMPROMETIDO], bloquear_filas=True
        )
        pendientes = [
            item for c in comprometidos for item in c.items if item.cantidad_pendiente > 0
        ]
        inventarios = self.inventario.bloquear_por_ids(
            {item.inventario_recurso_id for item in pendientes}
        )
        liberaciones = [
            self._liberar(
                item,
                inventarios[item.inventario_recurso_id],
                item.cantidad_pendiente,
                origen=OrigenActividad.CIERRE,
                referencia=None,
                fecha=fecha,
                observaciones=datos.get("observaciones"),
                autor=autor,
            )
            for item in pendientes
        ]
        for compromiso in comprometidos:
            compromiso.transicionar(EstadoCompromiso.FINALIZADO)
        db.session.commit()
        log.info(
            "Recursos de la emergencia liberados",
            extra={
                "contexto": {
                    "emergencia": emergencia,
                    "liberaciones": len(liberaciones),
                    "compromisos_finalizados": [c.id for c in comprometidos],
                }
            },
        )
        return self._estado(emergencia) | {"liberaciones": liberaciones}

    def cerrar_proyecto(
        self, emergencia: str, datos: dict, autor: str
    ) -> tuple[CierreProyecto, bool]:
        """*Cerrar proyecto*: registra el cierre si no queda nada comprometido. Devuelve
        (cierre, es_nuevo); repetirlo devuelve el cierre existente."""
        self._exigir_emergencia(emergencia)
        fecha = self._fecha_o_ahora(datos)
        if (cierre := self.liberaciones.cierre_de(emergencia)) is not None:
            return cierre, False

        self._iniciar_transaccion()
        # Bloquea también las reservas: una adjudicación en curso termina antes de decidir, y así
        # el cierre la ve como COMPROMETIDO y la rechaza
        vigentes = self.liberaciones.compromisos_de_emergencia(
            emergencia,
            estados=[EstadoCompromiso.RESERVADO, EstadoCompromiso.COMPROMETIDO],
            bloquear_filas=True,
        )
        if (cierre := self.liberaciones.cierre_de(emergencia)) is not None:
            db.session.commit()  # otro cierre entró mientras esperábamos el bloqueo
            return cierre, False
        comprometidos = [c for c in vigentes if c.estado == EstadoCompromiso.COMPROMETIDO]
        if comprometidos:
            raise Conflicto(
                "Quedan recursos comprometidos sin liberar: informá las actividades o liberá la "
                "emergencia antes de cerrarla.",
                codigo="RECURSOS_SIN_LIBERAR",
                detalles={"compromisos": [self._pendiente_de(c) for c in comprometidos]},
            )
        cierre = CierreProyecto(
            emergencia_referencia=emergencia,
            fecha_cierre=fecha,
            observaciones=datos.get("observaciones"),
            cerrado_por=autor,
        )
        self.liberaciones.agregar(cierre)
        try:
            db.session.commit()
        except IntegrityError:
            # Dos cierres a la vez sin ninguna fila que los serialice: el UNIQUE frena al segundo
            db.session.rollback()
            return self.liberaciones.cierre_de(emergencia), False
        log.info(
            "Proyecto cerrado",
            extra={"contexto": {"emergencia": emergencia, "reservas_vigentes": len(vigentes)}},
        )
        return cierre, True

    # --- Consultas -----------------------------------------------------------------------------

    def obtener_actividad(self, actividad_id: int) -> Actividad:
        actividad = self.liberaciones.obtener_actividad(actividad_id)
        if actividad is None:
            raise NoEncontrado("La actividad no existe.")
        return actividad

    def listar_actividades(
        self, filtros: dict, pagina: int, tamano: int
    ) -> tuple[list[Actividad], int]:
        return self.liberaciones.listar_actividades(pagina, tamano, **filtros)

    # --- Auxiliares ----------------------------------------------------------------------------

    def _iniciar_transaccion(self) -> None:
        iniciar_transaccion_con_bloqueos(self.lock_timeout_ms)

    def _validar(self, datos: dict) -> None:
        """Catálogo, unidad y fecha: todo lo que no necesita el compromiso ni bloqueos."""
        tipo = self.inventario.tipos_por_codigo({datos["tipo_recurso"]}).get(datos["tipo_recurso"])
        if tipo is None or not tipo.activo:
            raise ReglaDeNegocio(
                "El tipo de recurso no existe en el catálogo nacional.",
                codigo="TIPO_RECURSO_DESCONOCIDO",
                detalles={"tipos_recurso": [datos["tipo_recurso"]]},
            )
        if not tipo.unidad_medida.admite(datos["cantidad"]):
            raise ReglaDeNegocio(
                "Hay campos con errores.",
                detalles={"json": {"cantidad": ["Tiene que ser un número entero."]}},
            )
        self._exigir_fecha(datos["fecha"])

    @staticmethod
    def _exigir_fecha(fecha: datetime) -> None:
        if es_fecha_futura(fecha, ahora()):
            raise ReglaDeNegocio(
                "La fecha no puede ser futura.",
                codigo="FECHA_FUTURA",
                detalles={"fecha": fecha.isoformat()},
            )

    def _fecha_o_ahora(self, datos: dict) -> datetime:
        """La liberación y el cierre los dispara el sistema: si no traen fecha, es ahora."""
        fecha = datos.get("fecha")
        if fecha is None:
            return ahora()
        self._exigir_fecha(fecha)
        return fecha

    def _exigir_emergencia(self, emergencia: str) -> None:
        if not self.liberaciones.existe_emergencia(emergencia):
            raise NoEncontrado(
                "El Sistema Nacional no conoce esa emergencia: ninguna convocatoria la nombra.",
                detalles={"emergencia_referencia": emergencia},
            )

    def _estado(self, emergencia: str) -> dict:
        compromisos = self.liberaciones.compromisos_de_emergencia(emergencia)
        cierre = self.liberaciones.cierre_de(emergencia)
        return {
            "emergencia_referencia": emergencia,
            "todo_liberado": all(
                c.estado != EstadoCompromiso.COMPROMETIDO or c.todo_liberado() for c in compromisos
            ),
            "cerrado": cierre is not None,
            "cierre": cierre,
            "reservas_vigentes": sum(c.estado == EstadoCompromiso.RESERVADO for c in compromisos),
            "compromisos": compromisos,
        }

    @staticmethod
    def _pendiente_de(compromiso: Compromiso) -> dict:
        return {
            "id": compromiso.id,
            "oferta_referencia": compromiso.oferta_referencia,
            "ong_cuit": compromiso.ong.cuit,
            "pendiente": {
                item.tipo_recurso.codigo: str(item.cantidad_pendiente)
                for item in compromiso.items
                if item.cantidad_pendiente > 0
            },
        }

    def _previa(self, datos: dict) -> Actividad | None:
        """La actividad ya registrada con esa referencia, si existe. Si existe pero con otros
        datos, no es un reintento: es un conflicto."""
        previa = self.liberaciones.actividad_por_referencia(datos["actividad_referencia"])
        if previa is not None and not previa.coincide_con(datos):
            raise Conflicto(
                "Ya existe una actividad con esa referencia y otros datos.",
                codigo="ACTIVIDAD_DUPLICADA",
                detalles={"actividad_id": previa.id},
            )
        return previa

    def _exigir_proyecto_abierto(self, emergencia: str) -> None:
        cierre = self.liberaciones.cierre_de(emergencia)
        if cierre is not None:
            raise Conflicto(
                "El proyecto de la emergencia ya está cerrado.",
                codigo="PROYECTO_CERRADO",
                detalles={"fecha_cierre": cierre.fecha_cierre.isoformat()},
            )

    def _ong(self, cuit: str) -> ONG:
        """La ONG se identifica por CUIT en todos los contratos de la API (como en I-3.3 y 3.4)."""
        ong = self.ongs.por_cuit(cuit)
        if ong is None:
            raise ReglaDeNegocio(
                "La ONG no está registrada en el Sistema Nacional.",
                codigo="ONG_INEXISTENTE",
                detalles={"json": {"ong_cuit": ["No hay una ONG registrada con ese CUIT."]}},
            )
        return ong

    def _resolver_candidato(self, datos: dict) -> ItemCandidato:
        """Ubica el ítem por emergencia, ONG y categoría; `oferta_referencia` desambigua si la ONG
        tiene más de un compromiso ahí (una oferta propia y un consorcio, por ejemplo)."""
        self._ong(datos["ong_cuit"])
        candidatos = self.liberaciones.candidatos(
            datos["emergencia_referencia"],
            datos["ong_cuit"],
            datos["tipo_recurso"],
            datos.get("oferta_referencia"),
        )
        if not candidatos:
            raise NoEncontrado(
                "La ONG no tiene un compromiso con esa categoría en esa emergencia.",
                detalles={
                    "emergencia_referencia": datos["emergencia_referencia"],
                    "ong_cuit": datos["ong_cuit"],
                    "tipo_recurso": datos["tipo_recurso"],
                },
            )
        comprometidos = [c for c in candidatos if c.estado == EstadoCompromiso.COMPROMETIDO]
        if not comprometidos:
            raise TransicionInvalida(
                "Solo se liberan recursos de un compromiso COMPROMETIDO.",
                detalles={
                    "compromisos": [
                        {"id": c.compromiso_id, "oferta_referencia": c.oferta_referencia}
                        | {"estado": str(c.estado)}
                        for c in candidatos
                    ]
                },
            )
        if len(comprometidos) > 1:
            raise ReglaDeNegocio(
                "La ONG tiene más de un compromiso con esa categoría en la emergencia: indicá "
                "oferta_referencia.",
                codigo="COMPROMISO_AMBIGUO",
                detalles={"ofertas": [c.oferta_referencia for c in comprometidos]},
            )
        return comprometidos[0]

    def _compromiso_bloqueado(self, compromiso_id: int) -> Compromiso:
        compromiso = self.compromisos.obtener(compromiso_id, bloquear_fila=True)
        if compromiso is None:
            raise NoEncontrado("El compromiso no existe.")
        return compromiso

    @staticmethod
    def _exigir_comprometido(compromiso: Compromiso) -> None:
        """Se repite con la fila bloqueada: otra operación pudo finalizarlo mientras tanto."""
        if compromiso.estado != EstadoCompromiso.COMPROMETIDO:
            raise TransicionInvalida(
                "Solo se liberan recursos de un compromiso COMPROMETIDO.",
                detalles={"compromiso_id": compromiso.id, "estado": str(compromiso.estado)},
            )

    @staticmethod
    def _exigir_pendiente(item: CompromisoItem, cantidad: Decimal) -> None:
        """Con las filas bloqueadas: lo pendiente no puede cambiar hasta el commit."""
        if cantidad > item.cantidad_pendiente:
            raise Conflicto(
                "La cantidad supera lo comprometido que falta liberar.",
                codigo="EXCEDE_PENDIENTE",
                detalles={
                    "tipo_recurso": item.tipo_recurso.codigo,
                    "pedida": str(cantidad),
                    "pendiente": str(item.cantidad_pendiente),
                },
            )

    def _liberar(
        self,
        item: CompromisoItem,
        inventario: InventarioRecurso,
        cantidad: Decimal,
        *,
        origen: OrigenActividad,
        referencia: str | None,
        fecha: datetime,
        observaciones: str | None,
        autor: str,
    ) -> Actividad:
        """Descuenta del inventario y del ítem en la misma transacción, con los dos bloqueados:
        así los contadores vivos y el historial nunca se desincronizan."""
        actividad = Actividad(
            referencia=referencia,
            item=item,
            origen=origen,
            accion=aplicar_en_inventario(inventario, cantidad),
            cantidad=cantidad,
            fecha_cumplimiento=fecha,
            observaciones=observaciones,
            registrada_por=autor,
        )
        item.cantidad_liberada += cantidad
        self.liberaciones.agregar(actividad)
        return actividad

    @staticmethod
    def _registrar(evento: str, actividad: Actividad) -> None:
        contexto = {
            "actividad_id": actividad.id,
            "referencia": actividad.referencia,
            "compromiso_id": actividad.item.compromiso_id,
            "accion": str(actividad.accion),
            "cantidad": str(actividad.cantidad),
            "estado_compromiso": str(actividad.item.compromiso.estado),
        }
        log.info(evento, extra={"contexto": contexto})
