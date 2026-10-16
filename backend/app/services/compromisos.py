"""Casos de uso de I-3.4: validar restricciones y bloquear o comprometer recursos de las ONGs.

Flujo (acordado por el equipo):
- La webapp reserva cuando la ONG presenta la oferta, ajusta la reserva si la modifica y la cancela
  si la retira.
- Bonita confirma lo adjudicado. En una adjudicación parcial, la diferencia se libera en ese
  momento.
- Lo que no se adjudica vence al terminar la ventana de adjudicación de su convocatoria.

Cada operación que cambia el inventario corre en una transacción que bloquea las filas
involucradas (SELECT ... FOR UPDATE). Así dos pedidos simultáneos no pueden reservar más de lo que
hay. Las reglas de orden y el tope de espera están en app/repositories/bloqueos.py.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal

from app.errors import (
    Conflicto,
    NoEncontrado,
    RecursoOcupado,
    RecursosInsuficientes,
    ReglaDeNegocio,
)
from app.extensions import db
from app.models import (
    ONG,
    Compromiso,
    CompromisoItem,
    Convocatoria,
    EstadoCompromiso,
    InventarioRecurso,
    TipoRecurso,
)
from app.models.comun import ahora
from app.repositories.bloqueos import iniciar_transaccion_con_bloqueos
from app.repositories.compromisos import CompromisoRepository, ConvocatoriaRepository
from app.repositories.inventario import InventarioRepository
from app.repositories.ongs import ONGRepository

log = logging.getLogger(__name__)

CERO = Decimal("0")


@dataclass(frozen=True)
class ItemPedido:
    tipo_recurso: TipoRecurso
    cantidad: Decimal


class CompromisoService:
    def __init__(
        self,
        compromisos: CompromisoRepository,
        convocatorias: ConvocatoriaRepository,
        inventario: InventarioRepository,
        ongs: ONGRepository,
        *,
        lock_timeout_ms: int,
    ):
        self.compromisos = compromisos
        self.convocatorias = convocatorias
        self.inventario = inventario
        self.ongs = ongs
        self.lock_timeout_ms = lock_timeout_ms

    # --- Validar restricciones -------------------------------------------------------------

    def verificar(self, datos: dict) -> dict:
        """Valida un pedido sin reservar nada.

        El resultado es por ítem y no binario: informa cuánto hay disponible. Puede cambiar antes de
        reservar; por eso la reserva vuelve a validar con las filas bloqueadas.
        """
        ong = self._ong(datos["ong_cuit"])
        items = self._items_validos(datos["items"])
        self._vencer_atrasados_de(ong.id, items)
        inventarios = self.inventario.de_ong(ong.id, [item.tipo_recurso.id for item in items])
        resultados = [
            self._resultado(item, inventarios.get(item.tipo_recurso.id)) for item in items
        ]
        return {
            "ong_cuit": ong.cuit,
            "ong_habilitada": ong.habilitada,
            "se_puede_reservar": ong.habilitada
            and all(resultado["resultado"] == "DISPONIBLE" for resultado in resultados),
            "items": resultados,
        }

    # --- Bloqueo: reservar, ajustar y cancelar -----------------------------------------------

    def reservar(self, datos: dict, autor: str) -> tuple[Compromiso, bool]:
        """Bloquea los recursos de una oferta presentada. Devuelve (compromiso, es_nuevo).

        Es idempotente por oferta y ONG: si la webapp reintenta el mismo pedido, devuelve el
        compromiso existente en lugar de reservar dos veces.
        """
        ong = self._ong_habilitada(datos["ong_cuit"])
        items = self._items_validos(datos["items"])
        convocatoria = self._convocatoria(datos["convocatoria"])
        self._exigir_ventana_abierta(convocatoria)
        self._vencer_atrasados_de(ong.id, items)

        self._iniciar_transaccion()
        inventarios = self.inventario.bloquear_de_ong(ong.id, [i.tipo_recurso.id for i in items])
        # Se busca recién con las filas bloqueadas: un reintento simultáneo ya ve el compromiso
        # que confirmó el otro pedido.
        existente = self.compromisos.por_oferta_y_ong(datos["oferta_referencia"], ong.id)
        if existente is not None:
            self._exigir_mismo_pedido(existente, convocatoria, items)
            db.session.commit()
            return existente, False
        self._exigir_disponibilidad(
            {item.tipo_recurso: item.cantidad for item in items}, inventarios
        )

        compromiso = Compromiso(
            convocatoria=convocatoria,
            ong=ong,
            oferta_referencia=datos["oferta_referencia"],
            creado_por=autor,
        )
        for item in items:
            inventario = inventarios[item.tipo_recurso.id]
            inventario.bloquear(item.cantidad)
            compromiso.items.append(self._nuevo_item(ong.id, inventario, item.cantidad))
        self.compromisos.agregar(compromiso)
        db.session.commit()
        self._registrar("Recursos reservados", compromiso)
        return compromiso, True

    def ajustar(self, compromiso_id: int, datos: dict) -> Compromiso:
        """La ONG modificó la oferta dentro de la ventana: la reserva pasa a ser la nueva."""
        items = self._items_validos(datos["items"])
        self._vencer_atrasados_de(self._compromiso(compromiso_id).ong_id, items)

        self._iniciar_transaccion()
        compromiso = self._compromiso(compromiso_id, bloquear_fila=True)
        if compromiso.estado != EstadoCompromiso.RESERVADO:
            raise Conflicto(
                "Solo se puede modificar una reserva vigente.",
                codigo="COMPROMISO_NO_MODIFICABLE",
                detalles={"estado": str(compromiso.estado)},
            )
        self._exigir_ventana_abierta(compromiso.convocatoria)

        actuales = {item.inventario_recurso.tipo_recurso_id: item for item in compromiso.items}
        pedidos = {item.tipo_recurso.id: item for item in items}
        inventarios = self.inventario.bloquear_de_ong(
            compromiso.ong_id, actuales.keys() | pedidos.keys()
        )
        # Solo hace falta disponibilidad para lo que aumenta
        adicionales = {}
        for tipo_id, pedido in pedidos.items():
            actual = actuales[tipo_id].cantidad_reservada if tipo_id in actuales else CERO
            if pedido.cantidad > actual:
                adicionales[pedido.tipo_recurso] = pedido.cantidad - actual
        self._exigir_disponibilidad(adicionales, inventarios)

        for tipo_id, item in actuales.items():
            if tipo_id not in pedidos:
                inventarios[tipo_id].desbloquear(item.cantidad_reservada)
                compromiso.items.remove(item)
        for tipo_id, pedido in pedidos.items():
            inventario = inventarios[tipo_id]
            item = actuales.get(tipo_id)
            if item is None:
                inventario.bloquear(pedido.cantidad)
                compromiso.items.append(
                    self._nuevo_item(compromiso.ong_id, inventario, pedido.cantidad)
                )
                continue
            diferencia = pedido.cantidad - item.cantidad_reservada
            if diferencia > 0:
                inventario.bloquear(diferencia)
            else:
                inventario.desbloquear(-diferencia)
            item.cantidad_reservada = pedido.cantidad
        db.session.commit()
        self._registrar("Reserva ajustada", compromiso)
        return compromiso

    def cancelar(self, compromiso_id: int) -> Compromiso:
        """La ONG retiró la oferta: la reserva se cancela y los recursos vuelven a estar libres."""
        self._iniciar_transaccion()
        compromiso = self._compromiso(compromiso_id, bloquear_fila=True)
        if compromiso.estado == EstadoCompromiso.CANCELADO:
            db.session.commit()  # reintento: ya estaba cancelada
            return compromiso
        compromiso.transicionar(EstadoCompromiso.CANCELADO)
        self._liberar_reserva(compromiso)
        db.session.commit()
        self._registrar("Reserva cancelada", compromiso)
        return compromiso

    # --- Compromiso al adjudicar ---------------------------------------------------------------

    def confirmar(self, compromiso_id: int, datos: dict) -> Compromiso:
        """El municipio adjudicó: lo adjudicado queda comprometido y la diferencia se libera."""
        self._iniciar_transaccion()
        compromiso = self._compromiso(compromiso_id, bloquear_fila=True)
        adjudicado = self._cantidades_adjudicadas(compromiso, datos["items"])
        if (
            compromiso.estado == EstadoCompromiso.COMPROMETIDO
            and compromiso.cantidades_comprometidas() == adjudicado
        ):
            db.session.commit()  # reintento de Bonita con la misma adjudicación
            return compromiso
        if compromiso.vencio(ahora()):
            self._vencer(compromiso)
            db.session.commit()
            raise Conflicto(
                "Terminó la ventana de adjudicación: la reserva venció y liberó sus recursos.",
                codigo="RESERVA_VENCIDA",
                detalles={
                    "fecha_limite_adjudicacion": (
                        compromiso.convocatoria.fecha_limite_adjudicacion.isoformat()
                    )
                },
            )
        compromiso.transicionar(EstadoCompromiso.COMPROMETIDO)
        inventarios = self.inventario.bloquear_por_ids(
            [item.inventario_recurso_id for item in compromiso.items]
        )
        for item in compromiso.items:
            cantidad = adjudicado[item.tipo_recurso.codigo]
            inventarios[item.inventario_recurso_id].comprometer(item.cantidad_reservada, cantidad)
            item.cantidad_comprometida = cantidad
        db.session.commit()
        self._registrar("Recursos comprometidos", compromiso)
        return compromiso

    # --- Vencimiento ---------------------------------------------------------------------------

    def vencer_atrasados(
        self, *, inventario_ids: list[int] | None = None, convocatoria_id: int | None = None
    ) -> int:
        """Vence las reservas cuya ventana de adjudicación terminó y libera sus recursos.

        Cada reserva se vence en su propia transacción. Las que otra operación tiene bloqueadas se
        saltean: se vencen en la próxima pasada. Devuelve cuántas venció.
        """
        vencidas = 0
        ids = self.compromisos.ids_vencidos(
            ahora(), inventario_ids=inventario_ids, convocatoria_id=convocatoria_id
        )
        for compromiso_id in ids:
            try:
                self._iniciar_transaccion()
                compromiso = self.compromisos.obtener(
                    compromiso_id, bloquear_fila=True, saltear_ocupado=True
                )
                if compromiso is not None and compromiso.vencio(ahora()):
                    self._vencer(compromiso)
                    vencidas += 1
                db.session.commit()
            except RecursoOcupado:
                db.session.rollback()
        return vencidas

    # --- Consultas -----------------------------------------------------------------------------

    def obtener(self, compromiso_id: int) -> Compromiso:
        return self._compromiso(compromiso_id)

    def listar(self, filtros: dict, pagina: int, tamano: int) -> tuple[list[Compromiso], int]:
        return self.compromisos.listar(pagina, tamano, **filtros)

    # --- Auxiliares ----------------------------------------------------------------------------

    def _iniciar_transaccion(self) -> None:
        iniciar_transaccion_con_bloqueos(self.lock_timeout_ms)

    def _compromiso(self, compromiso_id: int, *, bloquear_fila: bool = False) -> Compromiso:
        compromiso = self.compromisos.obtener(compromiso_id, bloquear_fila=bloquear_fila)
        if compromiso is None:
            raise NoEncontrado("El compromiso no existe.")
        return compromiso

    def _ong(self, cuit: str) -> ONG:
        """La ONG se identifica por CUIT en todos los contratos de la API (como en I-3.3)."""
        ong = self.ongs.por_cuit(cuit)
        if ong is None:
            raise ReglaDeNegocio(
                "La ONG no está registrada en el Sistema Nacional.",
                codigo="ONG_INEXISTENTE",
                detalles={"json": {"ong_cuit": ["No hay una ONG registrada con ese CUIT."]}},
            )
        return ong

    def _ong_habilitada(self, cuit: str) -> ONG:
        ong = self._ong(cuit)
        if not ong.habilitada:
            raise ReglaDeNegocio(
                "La ONG no está habilitada para comprometer recursos.",
                codigo="ONG_NO_HABILITADA",
                detalles={"estado": str(ong.estado)},
            )
        return ong

    def _items_validos(self, items: list[dict]) -> list[ItemPedido]:
        """Tipo de recurso del catálogo y activo, sin repetir, y cantidad entera si la unidad no
        admite decimales (personas, raciones, kits)."""
        tipos = self.inventario.tipos_por_codigo({item["tipo_recurso"] for item in items})
        errores, vistos, validos = {}, set(), []
        for posicion, item in enumerate(items):
            codigo, cantidad = item["tipo_recurso"], item["cantidad"]
            tipo = tipos.get(codigo)
            if tipo is None or not tipo.activo:
                errores[posicion] = {"tipo_recurso": ["No existe en el catálogo."]}
            elif codigo in vistos:
                errores[posicion] = {"tipo_recurso": ["Está repetido en el pedido."]}
            elif not self._admite(tipo, cantidad):
                errores[posicion] = {"cantidad": ["Tiene que ser un número entero."]}
            else:
                validos.append(ItemPedido(tipo, cantidad))
            vistos.add(codigo)
        if errores:
            raise ReglaDeNegocio("Hay ítems con errores.", detalles={"json": {"items": errores}})
        return validos

    def _cantidades_adjudicadas(self, compromiso: Compromiso, items: list[dict]) -> dict:
        """Cantidad adjudicada por tipo de recurso. Lo que no se nombra se adjudica en 0."""
        reservado = compromiso.cantidades_reservadas()
        tipos = {item.tipo_recurso.codigo: item.tipo_recurso for item in compromiso.items}
        adjudicado = dict.fromkeys(reservado, CERO)
        errores, vistos = {}, set()
        for posicion, item in enumerate(items):
            codigo, cantidad = item["tipo_recurso"], item["cantidad"]
            if codigo not in reservado:
                errores[posicion] = {"tipo_recurso": ["No forma parte de la reserva."]}
            elif codigo in vistos:
                errores[posicion] = {"tipo_recurso": ["Está repetido en el pedido."]}
            elif cantidad > reservado[codigo]:
                errores[posicion] = {
                    "cantidad": [f"No puede superar lo reservado ({reservado[codigo]})."]
                }
            elif not self._admite(tipos[codigo], cantidad):
                errores[posicion] = {"cantidad": ["Tiene que ser un número entero."]}
            else:
                adjudicado[codigo] = cantidad
            vistos.add(codigo)
        if errores:
            raise ReglaDeNegocio("Hay ítems con errores.", detalles={"json": {"items": errores}})
        if not any(cantidad > 0 for cantidad in adjudicado.values()):
            raise ReglaDeNegocio(
                "La adjudicación no incluye ningún recurso. Si la oferta no se adjudica, su "
                "reserva vence sola al terminar la ventana de adjudicación."
            )
        return adjudicado

    @staticmethod
    def _admite(tipo: TipoRecurso, cantidad: Decimal) -> bool:
        return tipo.unidad_medida.admite_decimales or cantidad == cantidad.to_integral_value()

    def _convocatoria(self, datos: dict) -> Convocatoria:
        """Registra la convocatoria la primera vez que una reserva la nombra. Después, sus fechas
        solo cambian con PUT /convocatorias/{referencia}."""
        convocatoria = self.convocatorias.asegurar(
            datos["referencia"],
            datos["emergencia_referencia"],
            datos["fecha_cierre"],
            datos["fecha_limite_adjudicacion"],
        )
        db.session.commit()
        return convocatoria

    @staticmethod
    def _exigir_ventana_abierta(convocatoria: Convocatoria) -> None:
        if convocatoria.fecha_cierre <= ahora():
            raise Conflicto(
                "La convocatoria ya no recibe ofertas: no se puede reservar ni modificar recursos.",
                codigo="VENTANA_CERRADA",
                detalles={"fecha_cierre": convocatoria.fecha_cierre.isoformat()},
            )

    @staticmethod
    def _exigir_mismo_pedido(
        existente: Compromiso, convocatoria: Convocatoria, items: list[ItemPedido]
    ) -> None:
        pedido = {item.tipo_recurso.codigo: item.cantidad for item in items}
        if existente.convocatoria_id != convocatoria.id or (
            existente.cantidades_reservadas() != pedido
        ):
            raise Conflicto(
                "Ya existe un compromiso para esta oferta y ONG con otros datos. Para cambiar la "
                "reserva, usá PUT /compromisos/{id}.",
                codigo="COMPROMISO_EXISTENTE",
                detalles={"compromiso_id": existente.id, "estado": str(existente.estado)},
            )

    @staticmethod
    def _exigir_disponibilidad(
        necesario: dict[TipoRecurso, Decimal], inventarios: dict[int, InventarioRecurso]
    ) -> None:
        """Con las filas ya bloqueadas: nadie puede cambiar la disponibilidad hasta el commit."""
        faltantes = []
        for tipo, cantidad in necesario.items():
            inventario = inventarios.get(tipo.id)
            disponible = max(inventario.cantidad_disponible, CERO) if inventario else CERO
            if cantidad > disponible:
                faltantes.append(
                    {
                        "tipo_recurso": tipo.codigo,
                        "solicitado": str(cantidad),
                        "disponible": str(disponible),
                    }
                )
        if faltantes:
            raise RecursosInsuficientes(
                "La ONG no tiene disponible lo que se pide reservar.",
                detalles={"items": faltantes},
            )

    @staticmethod
    def _resultado(item: ItemPedido, inventario: InventarioRecurso | None) -> dict:
        disponible = max(inventario.cantidad_disponible, CERO) if inventario else CERO
        if disponible >= item.cantidad:
            resultado = "DISPONIBLE"
        elif disponible > 0:
            resultado = "PARCIAL"
        else:
            resultado = "SIN_DISPONIBILIDAD"
        return {
            "tipo_recurso": item.tipo_recurso.codigo,
            "solicitado": item.cantidad,
            "disponible": disponible,
            "resultado": resultado,
        }

    @staticmethod
    def _nuevo_item(
        ong_id: int, inventario: InventarioRecurso, cantidad: Decimal
    ) -> CompromisoItem:
        # ong_id se copia a mano: lo exigen las dos FK compuestas del ítem
        return CompromisoItem(
            ong_id=ong_id, inventario_recurso=inventario, cantidad_reservada=cantidad
        )

    def _liberar_reserva(self, compromiso: Compromiso) -> None:
        """Devuelve lo reservado. Se llama con el compromiso ya bloqueado."""
        inventarios = self.inventario.bloquear_por_ids(
            [item.inventario_recurso_id for item in compromiso.items]
        )
        for item in compromiso.items:
            inventarios[item.inventario_recurso_id].desbloquear(item.cantidad_reservada)

    def _vencer(self, compromiso: Compromiso) -> None:
        compromiso.transicionar(EstadoCompromiso.VENCIDO)
        self._liberar_reserva(compromiso)
        self._registrar("Reserva vencida", compromiso)

    def _vencer_atrasados_de(self, ong_id: int, items: list[ItemPedido]) -> None:
        """Antes de mirar la disponibilidad, vence las reservas atrasadas de esos recursos."""
        filas = self.inventario.de_ong(ong_id, [item.tipo_recurso.id for item in items])
        if filas:
            self.vencer_atrasados(inventario_ids=[fila.id for fila in filas.values()])

    @staticmethod
    def _registrar(evento: str, compromiso: Compromiso) -> None:
        contexto = {
            "compromiso_id": compromiso.id,
            "ong_id": compromiso.ong_id,
            "oferta": compromiso.oferta_referencia,
            "estado": str(compromiso.estado),
        }
        log.info(evento, extra={"contexto": contexto})
