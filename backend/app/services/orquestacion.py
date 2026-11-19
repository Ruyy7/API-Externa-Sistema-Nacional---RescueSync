"""Operaciones que Bonita invoca como orquestador del proceso (docs/08-orquestacion-bonita.md).

Principio de integración de la cátedra: la validación, el bloqueo/compromiso y la liberación los
invoca solo Bonita. La webapp no llama a estos servicios: Bonita le pide los datos, los trae acá y
le devuelve el resultado. Cada operación resuelve un paso del proceso en una sola llamada y una
sola transacción, así alcanza con un conector y nunca queda un paso aplicado a medias:

- *Validar ofertas*: valida por niveles de competencia [I-3.3] y bloquea lo aceptado [I-3.4].
- *Reabrir convocatoria* y *Reformular lotes*: liberan los bloqueos de la emergencia.
- *Comprometer recursos*: compromete lo adjudicado y libera lo que no se adjudicó.
- *Marcar actividad como finalizada*: registra las actividades cumplidas y libera sus recursos.

Todas son idempotentes: si Bonita reintenta un conector, el resultado es el mismo. Usan el
locking de I-3.4 (repositories/bloqueos.py): primero los compromisos y después el inventario,
siempre en orden de id.
"""

import logging
from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal

from app.errors import Conflicto, NoEncontrado, ReglaDeNegocio
from app.extensions import db
from app.models import (
    ONG,
    Compromiso,
    CompromisoItem,
    EstadoCompromiso,
    InventarioRecurso,
    MotivoNivel,
    TipoRecurso,
)
from app.models.comun import ahora
from app.repositories.bloqueos import iniciar_transaccion_con_bloqueos
from app.repositories.compromisos import CompromisoRepository, ConvocatoriaRepository
from app.repositories.inventario import InventarioRepository
from app.repositories.liberaciones import LiberacionRepository
from app.repositories.ongs import ONGRepository
from app.services.compromisos import CompromisoService
from app.services.liberaciones import LiberacionService
from app.services.validaciones import evaluar_linea, nivel_de_oferta

log = logging.getLogger(__name__)

CERO = Decimal("0")
RESERVADO, CANCELADO = EstadoCompromiso.RESERVADO, EstadoCompromiso.CANCELADO
ADJUDICADOS = (EstadoCompromiso.COMPROMETIDO, EstadoCompromiso.FINALIZADO)

# (oferta, id de la ONG) -> {id del tipo de recurso: cantidad aceptada}
Aceptado = dict[tuple[str, int], dict[int, Decimal]]
# (id de la ONG, id del tipo de recurso) -> fila de inventario bloqueada
Inventario = dict[tuple[int, int], InventarioRecurso]


class OrquestacionService:
    def __init__(
        self,
        compromisos: CompromisoRepository,
        convocatorias: ConvocatoriaRepository,
        inventario: InventarioRepository,
        ongs: ONGRepository,
        liberaciones: LiberacionRepository,
        servicio_de_compromisos: CompromisoService,
        servicio_de_liberaciones: LiberacionService,
        *,
        lock_timeout_ms: int,
    ):
        self.compromisos = compromisos
        self.convocatorias = convocatorias
        self.inventario = inventario
        self.ongs = ongs
        self.liberaciones = liberaciones
        self.servicio_de_compromisos = servicio_de_compromisos
        self.servicio_de_liberaciones = servicio_de_liberaciones
        self.lock_timeout_ms = lock_timeout_ms

    # --- Validar ofertas: validación y bloqueo -------------------------------------------------

    def validar_y_bloquear(self, emergencia: str, pedido: dict, autor: str) -> dict:
        """Valida las ofertas de la convocatoria y deja bloqueado lo que acepta.

        Con las filas de inventario bloqueadas, cada línea se acepta hasta lo que la ONG tiene
        disponible, y eso mismo queda reservado: entre la validación y la adjudicación ninguna
        otra emergencia puede llevarse esos recursos. A diferencia de POST /validaciones, que
        evalúa cada oferta por separado, acá las ofertas se evalúan en orden: lo que acepta una
        ya no está disponible para la siguiente de la misma ONG.

        Reemplaza los bloqueos anteriores de la convocatoria. Por eso sirve para el reintento de
        Bonita y para la nueva validación de una convocatoria reabierta: lo que ya no se acepta
        se libera.
        """
        lineas = [linea for oferta in pedido["ofertas"] for linea in oferta["items"]]
        tipos = self._tipos_del_catalogo({linea["tipo_recurso"] for linea in lineas})
        ongs = self.ongs.por_cuits({linea["ong_cuit"] for linea in lineas})
        self._exigir_proyecto_abierto(emergencia)
        convocatoria_id = self._registrar_convocatoria(emergencia, pedido)
        ong_ids = {ong.id for ong in ongs.values()}
        tipo_ids = {tipo.id for tipo in tipos.values()}
        # Antes de mirar la disponibilidad se vencen las reservas atrasadas de esos recursos
        if inventario_ids := self.inventario.ids_de_ongs(ong_ids, tipo_ids):
            self.servicio_de_compromisos.vencer_atrasados(inventario_ids=inventario_ids)

        self._iniciar_transaccion()
        existentes = self.compromisos.de_convocatoria(convocatoria_id, bloquear_filas=True)
        if any(compromiso.estado in ADJUDICADOS for compromiso in existentes):
            raise Conflicto(
                "La convocatoria ya se adjudicó: sus recursos están comprometidos.",
                codigo="CONVOCATORIA_ADJUDICADA",
            )
        ofertas_pedidas = {oferta["oferta_referencia"] for oferta in pedido["ofertas"]}
        if ajenas := self.compromisos.ofertas_de_otra_convocatoria(
            ofertas_pedidas, convocatoria_id
        ):
            raise Conflicto(
                "Hay ofertas que ya tienen recursos bloqueados en otra convocatoria.",
                codigo="COMPROMISO_EXISTENTE",
                detalles={"ofertas": ajenas},
            )
        vigentes = [compromiso for compromiso in existentes if compromiso.estado == RESERVADO]
        filas = self.inventario.bloquear_de_ongs(
            ong_ids,
            tipo_ids,
            ademas={item.inventario_recurso_id for c in vigentes for item in c.items},
        )
        # Lo que esta convocatoria tenía bloqueado vuelve a contar como disponible para
        # evaluarla de nuevo. Todo pasa dentro de la transacción: nadie lo ve libre.
        for compromiso in vigentes:
            for item in compromiso.items:
                filas[item.inventario_recurso_id].desbloquear(item.cantidad_reservada)
        inventario = {(fila.ong_id, fila.tipo_recurso_id): fila for fila in filas.values()}

        aceptado: Aceptado = defaultdict(lambda: defaultdict(Decimal))
        ofertas = [
            self._evaluar_y_bloquear(oferta, ongs, tipos, inventario, aceptado)
            for oferta in pedido["ofertas"]
        ]
        self._guardar_bloqueos(convocatoria_id, existentes, aceptado, ongs, inventario, autor)
        db.session.commit()
        log.info(
            "Ofertas validadas y recursos bloqueados",
            extra={
                "contexto": {
                    "emergencia": emergencia,
                    "convocatoria": pedido["convocatoria_referencia"],
                    "reservas": len(aceptado),
                    "niveles": {o["oferta_referencia"]: str(o["nivel"]) for o in ofertas},
                }
            },
        )
        return {
            "convocatoria_referencia": pedido["convocatoria_referencia"],
            "emergencia_referencia": emergencia,
            "ofertas": ofertas,
            "reservas": len(aceptado),
        }

    @staticmethod
    def _evaluar_y_bloquear(
        oferta: dict,
        ongs: dict[str, ONG],
        tipos: dict[str, TipoRecurso],
        inventario: Inventario,
        aceptado: Aceptado,
    ) -> dict:
        """Evalúa cada línea con la misma regla de I-3.3 (evaluar_linea) y bloquea lo aceptado
        en la fila de inventario, que ya está bloqueada con FOR UPDATE."""
        items = []
        for linea in oferta["items"]:
            ong = ongs.get(linea["ong_cuit"])
            tipo = tipos[linea["tipo_recurso"]]
            fila = inventario.get((ong.id, tipo.id)) if ong is not None else None
            if ong is None:
                impedimento = MotivoNivel.ONG_NO_REGISTRADA
            elif not ong.habilitada:
                impedimento = MotivoNivel.ONG_NO_HABILITADA
            elif fila is None:
                impedimento = MotivoNivel.NO_INSCRIPTA
            else:
                impedimento = None
            habilitada = max(fila.cantidad_disponible, CERO) if impedimento is None else CERO
            evaluacion = evaluar_linea(
                linea["cantidad_ofrecida"], linea["cantidad_requerida"], habilitada, impedimento
            )
            if evaluacion.cantidad_aceptada > 0:
                fila.bloquear(evaluacion.cantidad_aceptada)
                clave = (oferta["oferta_referencia"], ong.id)
                aceptado[clave][tipo.id] += evaluacion.cantidad_aceptada
            items.append({**linea, **asdict(evaluacion)})
        return {
            "oferta_referencia": oferta["oferta_referencia"],
            "nivel": nivel_de_oferta([item["nivel"] for item in items]),
            "items": items,
        }

    def _guardar_bloqueos(
        self,
        convocatoria_id: int,
        existentes: list[Compromiso],
        aceptado: Aceptado,
        ongs: dict[str, ONG],
        inventario: Inventario,
        autor: str,
    ) -> None:
        """Deja un compromiso RESERVADO por oferta y ONG con lo aceptado. Los contadores del
        inventario ya quedaron actualizados al evaluar: acá se guarda de quién es cada bloqueo."""
        por_clave = {(c.oferta_referencia, c.ong_id): c for c in existentes}
        ongs_por_id = {ong.id: ong for ong in ongs.values()}
        for (oferta_referencia, ong_id), cantidades in aceptado.items():
            compromiso = por_clave.pop((oferta_referencia, ong_id), None)
            if compromiso is None:
                compromiso = Compromiso(
                    convocatoria_id=convocatoria_id,
                    ong=ongs_por_id[ong_id],
                    oferta_referencia=oferta_referencia,
                    creado_por=autor,
                )
                self.compromisos.agregar(compromiso)
            elif compromiso.estado != RESERVADO:
                # Se había liberado al reabrir (o venció): la nueva validación lo bloquea otra vez
                compromiso.transicionar(RESERVADO)
            self._fijar_reserva(compromiso, ong_id, cantidades, inventario)
        # Lo que esta validación ya no acepta (o la oferta se retiró) queda liberado
        for compromiso in por_clave.values():
            if compromiso.estado == RESERVADO:
                compromiso.transicionar(CANCELADO)

    @staticmethod
    def _fijar_reserva(
        compromiso: Compromiso, ong_id: int, cantidades: dict[int, Decimal], inventario: Inventario
    ) -> None:
        actuales = {item.inventario_recurso.tipo_recurso_id: item for item in compromiso.items}
        for tipo_id, item in actuales.items():
            if tipo_id not in cantidades:
                compromiso.items.remove(item)
        for tipo_id, cantidad in cantidades.items():
            item = actuales.get(tipo_id)
            if item is None:
                # ong_id se copia a mano: lo exigen las dos FK compuestas del ítem
                compromiso.items.append(
                    CompromisoItem(
                        ong_id=ong_id,
                        inventario_recurso=inventario[(ong_id, tipo_id)],
                        cantidad_reservada=cantidad,
                    )
                )
            else:
                item.cantidad_reservada = cantidad

    # --- Reabrir o reformular: liberar los bloqueos --------------------------------------------

    def desbloquear(self, emergencia: str) -> dict:
        """Libera los recursos bloqueados de la emergencia que todavía no se adjudicaron.

        Bonita lo llama cuando el coordinador decide reabrir la convocatoria o reformular los
        lotes: las ofertas pueden cambiar, así que se validan y bloquean de nuevo cuando vence la
        nueva ventana. Si no hay nada bloqueado, no cambia nada.
        """
        self._iniciar_transaccion()
        reservados = self.liberaciones.compromisos_de_emergencia(
            emergencia, estados=[RESERVADO], bloquear_filas=True
        )
        filas = self.inventario.bloquear_por_ids(
            {item.inventario_recurso_id for c in reservados for item in c.items}
        )
        self._cancelar(reservados, filas)
        db.session.commit()
        log.info(
            "Bloqueos de la emergencia liberados",
            extra={"contexto": {"emergencia": emergencia, "reservas": len(reservados)}},
        )
        return {"emergencia_referencia": emergencia, "reservas_canceladas": len(reservados)}

    @staticmethod
    def _cancelar(reservados: list[Compromiso], filas: dict[int, InventarioRecurso]) -> None:
        """Con los compromisos y sus filas de inventario ya bloqueados."""
        for compromiso in reservados:
            compromiso.transicionar(CANCELADO)
            for item in compromiso.items:
                filas[item.inventario_recurso_id].desbloquear(item.cantidad_reservada)

    # --- Comprometer recursos ------------------------------------------------------------------

    def comprometer_adjudicacion(self, emergencia: str, datos: dict) -> dict:
        """Compromete lo que adjudicó el municipio y libera los bloqueos que no se adjudicaron.

        Todo o nada: si una adjudicación no es válida, no se compromete ninguna. Repetir la misma
        adjudicación no cambia nada (reintento de Bonita).
        """
        convocatoria = self.convocatorias.por_referencia(datos["convocatoria_referencia"])
        if convocatoria is None or convocatoria.emergencia_referencia != emergencia:
            raise NoEncontrado(
                "La emergencia no tiene una convocatoria validada con esa referencia.",
                detalles={
                    "emergencia_referencia": emergencia,
                    "convocatoria_referencia": datos["convocatoria_referencia"],
                },
            )
        convocatoria_id = convocatoria.id
        self._exigir_proyecto_abierto(emergencia)
        adjudicado = self._adjudicado_por_oferta_y_ong(datos["adjudicaciones"])

        self._iniciar_transaccion()
        compromisos = self.compromisos.de_convocatoria(convocatoria_id, bloquear_filas=True)
        filas = self.inventario.bloquear_por_ids(
            {item.inventario_recurso_id for c in compromisos for item in c.items}
        )
        por_clave = {(c.oferta_referencia, c.ong.cuit): c for c in compromisos}
        a_comprometer, errores = [], []
        for (oferta_referencia, cuit), cantidades in adjudicado.items():
            compromiso = por_clave.get((oferta_referencia, cuit))
            if error := self._error_de_adjudicacion(compromiso, cantidades):
                errores.append(
                    {"oferta_referencia": oferta_referencia, "ong_cuit": cuit, "error": error}
                )
            elif compromiso.estado == RESERVADO:
                a_comprometer.append((compromiso, cantidades))
            # Si ya estaba comprometido con esas cantidades es un reintento: no hay nada que hacer
        if errores:
            raise ReglaDeNegocio(
                "Hay adjudicaciones que no se pueden comprometer.",
                codigo="ADJUDICACION_INVALIDA",
                detalles={"adjudicaciones": errores},
            )
        momento = ahora()
        if any(compromiso.vencio(momento) for compromiso, _ in a_comprometer):
            raise Conflicto(
                "Terminó la ventana de adjudicación: los bloqueos vencieron.",
                codigo="RESERVA_VENCIDA",
                detalles={
                    "fecha_limite_adjudicacion": convocatoria.fecha_limite_adjudicacion.isoformat()
                },
            )

        for compromiso, cantidades in a_comprometer:
            compromiso.transicionar(EstadoCompromiso.COMPROMETIDO)
            for item in compromiso.items:
                cantidad = cantidades.get(item.tipo_recurso.codigo, CERO)
                filas[item.inventario_recurso_id].comprometer(item.cantidad_reservada, cantidad)
                item.cantidad_comprometida = cantidad
        sin_adjudicar = [compromiso for compromiso in compromisos if compromiso.estado == RESERVADO]
        self._cancelar(sin_adjudicar, filas)
        db.session.commit()
        comprometidos = [
            compromiso for compromiso in compromisos if compromiso.estado in ADJUDICADOS
        ]
        log.info(
            "Adjudicación comprometida",
            extra={
                "contexto": {
                    "emergencia": emergencia,
                    "convocatoria": datos["convocatoria_referencia"],
                    "comprometidos": [compromiso.id for compromiso in comprometidos],
                    "reservas_canceladas": len(sin_adjudicar),
                }
            },
        )
        return {
            "emergencia_referencia": emergencia,
            "convocatoria_referencia": datos["convocatoria_referencia"],
            "compromisos": comprometidos,
            "reservas_canceladas": len(sin_adjudicar),
        }

    @staticmethod
    def _adjudicado_por_oferta_y_ong(adjudicaciones: list[dict]) -> dict:
        """{(oferta, CUIT): {código de tipo: cantidad}}, solo con lo adjudicado en más de 0. Una
        oferta sin nada adjudicado no aparece: su bloqueo se libera."""
        adjudicado: dict = defaultdict(lambda: defaultdict(Decimal))
        for adjudicacion in adjudicaciones:
            clave = (adjudicacion["oferta_referencia"], adjudicacion["ong_cuit"])
            for item in adjudicacion["items"]:
                if item["cantidad"] > 0:
                    adjudicado[clave][item["tipo_recurso"]] += item["cantidad"]
        return {clave: dict(cantidades) for clave, cantidades in adjudicado.items()}

    @staticmethod
    def _error_de_adjudicacion(
        compromiso: Compromiso | None, cantidades: dict[str, Decimal]
    ) -> str | None:
        if compromiso is None or compromiso.estado not in (RESERVADO, *ADJUDICADOS):
            return "No tiene recursos bloqueados: la oferta no se validó o su bloqueo se liberó."
        if compromiso.estado in ADJUDICADOS:
            comprometido = {
                codigo: cantidad
                for codigo, cantidad in compromiso.cantidades_comprometidas().items()
                if cantidad > 0
            }
            return None if comprometido == cantidades else "Ya se adjudicó con otras cantidades."
        reservado = compromiso.cantidades_reservadas()
        tipos = {item.tipo_recurso.codigo: item.tipo_recurso for item in compromiso.items}
        for codigo, cantidad in cantidades.items():
            if codigo not in reservado:
                return f"{codigo} no está bloqueado para esta oferta."
            if cantidad > reservado[codigo]:
                return f"{codigo}: no puede superar lo bloqueado ({reservado[codigo]})."
            if not tipos[codigo].unidad_medida.admite(cantidad):
                return f"{codigo}: la cantidad tiene que ser un número entero."
        return None

    # --- Marcar actividad como finalizada ------------------------------------------------------

    def registrar_actividades(self, emergencia: str, actividades: list[dict], autor: str) -> dict:
        """Registra las actividades cumplidas que informa la webapp y libera sus recursos.

        Cada actividad se registra en su propia transacción y es idempotente por su referencia
        (LiberacionService.registrar_actividad). Si una falla, las anteriores quedan registradas
        y el reintento de Bonita sigue desde ahí sin liberar nada dos veces.
        """
        registradas, nuevas = [], 0
        for datos in actividades:
            actividad, es_nueva = self.servicio_de_liberaciones.registrar_actividad(
                {**datos, "emergencia_referencia": emergencia}, autor
            )
            registradas.append(actividad)
            nuevas += es_nueva
        return {"emergencia_referencia": emergencia, "nuevas": nuevas, "actividades": registradas}

    # --- Auxiliares ----------------------------------------------------------------------------

    def _iniciar_transaccion(self) -> None:
        iniciar_transaccion_con_bloqueos(self.lock_timeout_ms)

    def _tipos_del_catalogo(self, codigos: set[str]) -> dict[str, TipoRecurso]:
        tipos = self.inventario.tipos_por_codigo(codigos)
        if desconocidos := sorted(codigos - tipos.keys()):
            # Es un error de integración (catálogo desalineado), no de la ONG: falla todo el pedido
            raise ReglaDeNegocio(
                "Hay tipos de recurso que no existen en el catálogo nacional.",
                codigo="TIPO_RECURSO_DESCONOCIDO",
                detalles={"tipos_recurso": desconocidos},
            )
        return tipos

    def _registrar_convocatoria(self, emergencia: str, pedido: dict) -> int:
        """Registra la convocatoria la primera vez y actualiza sus fechas: después de una
        reapertura, los bloqueos vencen con la nueva ventana de adjudicación."""
        convocatoria = self.convocatorias.asegurar(
            pedido["convocatoria_referencia"],
            emergencia,
            pedido["fecha_cierre"],
            pedido["fecha_limite_adjudicacion"],
        )
        if convocatoria.emergencia_referencia != emergencia:
            raise Conflicto(
                "La convocatoria pertenece a otra emergencia.",
                codigo="CONVOCATORIA_DE_OTRA_EMERGENCIA",
                detalles={"emergencia_referencia": convocatoria.emergencia_referencia},
            )
        convocatoria.fecha_cierre = pedido["fecha_cierre"]
        convocatoria.fecha_limite_adjudicacion = pedido["fecha_limite_adjudicacion"]
        db.session.commit()
        return convocatoria.id

    def _exigir_proyecto_abierto(self, emergencia: str) -> None:
        cierre = self.liberaciones.cierre_de(emergencia)
        if cierre is not None:
            raise Conflicto(
                "El proyecto de la emergencia ya está cerrado.",
                codigo="PROYECTO_CERRADO",
                detalles={"fecha_cierre": cierre.fecha_cierre.isoformat()},
            )
