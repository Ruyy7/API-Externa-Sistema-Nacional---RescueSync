"""Registro (onboarding) de ONGs y gestión de sus categorías (I-3.1).

Aclaraciones del docente: la ONG se registra sola y nadie la aprueba después; al registrarse se
inscribe en categorías y declara el máximo de cada una. Como ya acordó el equipo (docs/03, correo
del 08/10), cada categoría es una fila de `inventario_recurso` y el máximo es su `cantidad_total`.
Por eso una ONG recién registrada ya puede validar (I-3.3) y reservar (I-3.4).
"""

from decimal import Decimal

from app.errors import Conflicto, NoEncontrado, ReglaDeNegocio
from app.extensions import db
from app.models import ONG, Cuenta, EstadoONG, InventarioRecurso, TipoRecurso
from app.repositories.bloqueos import iniciar_transaccion_con_bloqueos
from app.repositories.cuentas import CategoriaRepository, CuentaRepository
from app.repositories.inventario import InventarioRepository
from app.repositories.ongs import ONGRepository
from app.security import RolSistema
from app.services.auth import normalizar_usuario


class OnboardingService:
    def __init__(
        self,
        ongs: ONGRepository,
        cuentas: CuentaRepository,
        categorias: CategoriaRepository,
        inventario: InventarioRepository,
        *,
        lock_timeout_ms: int,
    ):
        self.ongs = ongs
        self.cuentas = cuentas
        self.categorias = categorias
        self.inventario = inventario
        self.lock_timeout_ms = lock_timeout_ms

    def registrar(self, datos: dict) -> ONG:
        """Crea la ONG habilitada, sus categorías y su cuenta en una sola transacción."""
        usuario = normalizar_usuario(datos["email_contacto"])
        if self.ongs.por_cuit(datos["cuit"]) is not None:
            raise Conflicto("Ya hay una ONG registrada con ese CUIT.", codigo="CUIT_DUPLICADO")
        if self.cuentas.por_usuario(usuario) is not None:
            raise Conflicto("Ya hay una cuenta con ese email.", codigo="USUARIO_DUPLICADO")
        maximos = self._maximos_por_tipo(datos["categorias"])

        # Sin aprobación posterior: la habilitación concreta la dan las categorías y sus topes
        ong = ONG(
            razon_social=datos["razon_social"],
            cuit=datos["cuit"],
            email_contacto=usuario,
            telefono=datos.get("telefono"),
            estado=EstadoONG.HABILITADA,
        )
        for tipo, maximo in maximos.items():
            ong.inventario.append(InventarioRecurso(tipo_recurso=tipo, cantidad_total=maximo))
        cuenta = Cuenta(usuario=usuario, rol=RolSistema.ONG, ong=ong)
        cuenta.definir_password(datos["password"])
        self.cuentas.agregar(cuenta)
        db.session.commit()
        return ong

    def mi_ong(self, cuit: str) -> ONG:
        ong = self.ongs.por_cuit(cuit)
        if ong is None:
            raise NoEncontrado("La ONG no existe.")
        return ong

    def actualizar_categorias(self, cuit: str, categorias: list[dict]) -> ONG:
        """Reemplaza las categorías y sus topes, sin dejar por debajo lo ya reservado o
        comprometido. Bloquea el inventario de la ONG como I-3.4, así una reserva simultánea no
        queda con un tope menor al que reservó."""
        ong = self.mi_ong(cuit)
        maximos = {tipo.id: maximo for tipo, maximo in self._maximos_por_tipo(categorias).items()}
        codigos = {fila.tipo_recurso_id: fila.tipo_recurso.codigo for fila in ong.inventario}
        actuales_ids = set(codigos)

        iniciar_transaccion_con_bloqueos(self.lock_timeout_ms)
        actuales = self.inventario.bloquear_de_ong(ong.id, actuales_ids | set(maximos))
        historial = self.categorias.con_historial([fila.id for fila in actuales.values()])

        errores = {}
        for tipo_id, fila in actuales.items():
            en_uso = fila.cantidad_bloqueada + fila.cantidad_comprometida
            codigo = codigos[tipo_id]
            if tipo_id in maximos:
                if maximos[tipo_id] < en_uso:
                    errores[codigo] = [
                        f"El tope no puede ser menor a {en_uso} (reservado más comprometido)."
                    ]
                else:
                    fila.cantidad_total = maximos[tipo_id]
            elif en_uso > 0 or fila.id in historial:
                errores[codigo] = [
                    "No se puede quitar: ya se usó en reservas. Podés bajar su tope a lo "
                    "comprometido."
                ]
            else:
                ong.inventario.remove(fila)
        if errores:
            raise Conflicto(
                "Hay categorías con recursos reservados o comprometidos.",
                codigo="CATEGORIA_EN_USO",
                detalles={"categorias": errores},
            )
        for tipo_id, maximo in maximos.items():
            if tipo_id not in actuales:
                ong.inventario.append(
                    InventarioRecurso(tipo_recurso_id=tipo_id, cantidad_total=maximo)
                )
        db.session.commit()
        db.session.refresh(ong)
        return ong

    def _maximos_por_tipo(self, categorias: list[dict]) -> dict[TipoRecurso, Decimal]:
        """Valida los códigos contra el catálogo nacional y las cantidades contra su unidad."""
        codigos = [categoria["tipo_recurso"] for categoria in categorias]
        repetidos = sorted({codigo for codigo in codigos if codigos.count(codigo) > 1})
        if repetidos:
            raise ReglaDeNegocio(
                "Cada categoría va una sola vez.", detalles={"tipos_recurso": repetidos}
            )
        tipos = self.inventario.tipos_por_codigo(codigos)
        desconocidos = sorted(set(codigos) - set(tipos))
        if desconocidos:
            raise ReglaDeNegocio(
                "Hay tipos de recurso que no existen en el catálogo nacional.",
                codigo="TIPO_RECURSO_DESCONOCIDO",
                detalles={"tipos_recurso": desconocidos},
            )
        enteras = sorted(
            categoria["tipo_recurso"]
            for categoria in categorias
            if not tipos[categoria["tipo_recurso"]].unidad_medida.admite_decimales
            and categoria["cantidad_maxima"] != categoria["cantidad_maxima"].to_integral_value()
        )
        if enteras:
            raise ReglaDeNegocio(
                "Esas categorías se cuentan en unidades enteras.",
                detalles={"tipos_recurso": enteras},
            )
        return {tipos[c["tipo_recurso"]]: c["cantidad_maxima"] for c in categorias}
