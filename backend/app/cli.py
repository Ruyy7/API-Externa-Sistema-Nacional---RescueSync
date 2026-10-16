"""Seed reproducible para demo del punto I-3.2."""

from datetime import date
from decimal import Decimal

import click
from flask import Flask
from sqlalchemy import select

from app.extensions import db
from app.models import (
    ONG,
    CategoriaRecurso,
    Certificacion,
    EstadoONG,
    InventarioRecurso,
    ONGCertificacion,
    TipoRecurso,
    UnidadMedida,
)
from app.security import RolSistema, emitir_token

# Los códigos de unidad y tipo de recurso son los mismos que usa RescueSync E2.
UNIDADES_DE_MEDIDA = [
    ("PERSONA", "Personas", False),
    ("RACION", "Raciones", False),
    ("LITRO", "Litros", True),
    ("KILOGRAMO", "Kilogramos", True),
    ("KIT", "Kits", False),
    ("UNIDAD", "Unidades", False),
]

PERSONAL, MATERIAL = CategoriaRecurso.PERSONAL, CategoriaRecurso.MATERIAL
# (codigo, nombre, categoria, unidad, reutilizable)
TIPOS_DE_RECURSO = [
    ("PARAMEDICO", "Paramédico", PERSONAL, "PERSONA", True),
    ("MEDICO", "Médico", PERSONAL, "PERSONA", True),
    ("ENFERMERO", "Enfermero", PERSONAL, "PERSONA", True),
    ("BOMBERO", "Bombero", PERSONAL, "PERSONA", True),
    ("RESCATISTA", "Rescatista", PERSONAL, "PERSONA", True),
    ("VOLUNTARIO_LOGISTICA", "Voluntario de logística", PERSONAL, "PERSONA", True),
    ("RACION_ALIMENTO", "Ración de alimento", MATERIAL, "RACION", False),
    ("AGUA_POTABLE", "Agua potable", MATERIAL, "LITRO", False),
    ("ALIMENTO_SECO", "Alimento no perecedero", MATERIAL, "KILOGRAMO", False),
    ("KIT_MEDICAMENTOS", "Kit de medicamentos", MATERIAL, "KIT", False),
    ("KIT_HIGIENE", "Kit de higiene", MATERIAL, "KIT", False),
    ("FRAZADA", "Frazada", MATERIAL, "UNIDAD", True),
    ("COLCHON", "Colchón", MATERIAL, "UNIDAD", True),
    ("CARPA", "Carpa", MATERIAL, "UNIDAD", True),
]


# El enunciado no fija un catálogo de certificaciones. Estos valores son solo datos de demo.
CERTIFICACIONES = [
    ("PRIMEROS_AUXILIOS", "Primeros auxilios"),
    ("RESCATE_ACUATICO", "Rescate acuático"),
    ("LOGISTICA_HUMANITARIA", "Logística humanitaria"),
    ("MANIPULACION_ALIMENTOS", "Manipulación segura de alimentos"),
]

ONGS = [
    ("Rescatistas del Río", "30-11111111-1", EstadoONG.HABILITADA),
    ("Alimentos Solidarios", "30-22222222-2", EstadoONG.HABILITADA),
    ("Ayuda en Registro", "30-33333333-3", EstadoONG.PENDIENTE),
]


def _obtener_o_crear(modelo, datos: dict, **clave):
    instancia = db.session.scalar(select(modelo).filter_by(**clave))
    if instancia is None:
        instancia = modelo(**clave, **datos)
        db.session.add(instancia)
    return instancia


def cargar_datos_demo() -> None:
    unidades = {
        codigo: _obtener_o_crear(
            UnidadMedida,
            {"nombre": nombre, "admite_decimales": admite},
            codigo=codigo,
        )
        for codigo, nombre, admite in UNIDADES_DE_MEDIDA
    }
    recursos = {}
    for codigo, nombre, categoria, unidad, reutilizable in TIPOS_DE_RECURSO:
        recursos[codigo] = _obtener_o_crear(
            TipoRecurso,
            {
                "nombre": nombre,
                "categoria": categoria,
                "unidad_medida": unidades[unidad],
                "reutilizable": reutilizable,
            },
            codigo=codigo,
        )
        recursos[codigo].nombre = nombre
        recursos[codigo].categoria = categoria
        recursos[codigo].unidad_medida = unidades[unidad]
        recursos[codigo].reutilizable = reutilizable

    certificaciones = {
        codigo: _obtener_o_crear(Certificacion, {"nombre": nombre}, codigo=codigo)
        for codigo, nombre in CERTIFICACIONES
    }
    ongs = {
        cuit: _obtener_o_crear(ONG, {"razon_social": nombre, "estado": estado}, cuit=cuit)
        for nombre, cuit, estado in ONGS
    }
    # Si el seed ya existía, dejamos los estados en el valor de demo esperado.
    for _, cuit, estado in ONGS:
        ongs[cuit].estado = estado

    # Las relaciones siguientes usan las PK generadas por PostgreSQL.
    db.session.flush()

    asociaciones = [
        ("30-11111111-1", "PRIMEROS_AUXILIOS", date(2025, 1, 10), date(2027, 1, 10)),
        ("30-11111111-1", "RESCATE_ACUATICO", date(2025, 4, 1), date(2027, 4, 1)),
        ("30-22222222-2", "LOGISTICA_HUMANITARIA", date(2025, 2, 15), None),
        ("30-22222222-2", "MANIPULACION_ALIMENTOS", date(2025, 3, 20), date(2027, 3, 20)),
    ]
    for cuit, codigo, emision, vencimiento in asociaciones:
        clave = {"ong_id": ongs[cuit].id, "certificacion_id": certificaciones[codigo].id}
        asignacion = db.session.scalar(select(ONGCertificacion).filter_by(**clave))
        if asignacion is None:
            asignacion = ONGCertificacion(
                ong=ongs[cuit],
                certificacion=certificaciones[codigo],
                fecha_emision=emision,
                fecha_vencimiento=vencimiento,
            )
            db.session.add(asignacion)
        else:
            asignacion.fecha_emision = emision
            asignacion.fecha_vencimiento = vencimiento

    # (cuit, recurso, total, bloqueado, comprometido). Separar reserva de adjudicación permite
    # evolucionar a locking transaccional sin cambiar el contrato de consulta.
    inventario = [
        ("30-11111111-1", "PARAMEDICO", "12", "2", "0"),
        ("30-11111111-1", "RESCATISTA", "20", "3", "2"),
        ("30-11111111-1", "FRAZADA", "300", "20", "30"),
        ("30-22222222-2", "RACION_ALIMENTO", "5000", "700", "300"),
        ("30-22222222-2", "AGUA_POTABLE", "2500", "300", "200"),
        ("30-22222222-2", "ALIMENTO_SECO", "1200", "100", "100"),
        # No debe entrar en la disponibilidad global por defecto por estar PENDIENTE.
        ("30-33333333-3", "PARAMEDICO", "100", "0", "0"),
    ]
    db.session.flush()
    for cuit, recurso, total, bloqueado, comprometido in inventario:
        clave = {"ong_id": ongs[cuit].id, "tipo_recurso_id": recursos[recurso].id}
        item = db.session.scalar(select(InventarioRecurso).filter_by(**clave))
        if item is None:
            item = InventarioRecurso(
                ong=ongs[cuit],
                tipo_recurso=recursos[recurso],
                cantidad_total=Decimal(total),
                cantidad_bloqueada=Decimal(bloqueado),
                cantidad_comprometida=Decimal(comprometido),
            )
            db.session.add(item)
        else:
            item.cantidad_total = Decimal(total)
            item.cantidad_bloqueada = Decimal(bloqueado)
            item.cantidad_comprometida = Decimal(comprometido)

    db.session.commit()


def registrar_comandos(app: Flask) -> None:
    @app.cli.command("seed")
    def seed() -> None:
        """Carga ONGs, certificaciones, tipos de recurso e inventario de demostración."""
        cargar_datos_demo()
        click.echo("Datos de demostración del Sistema Nacional cargados.")

    @app.cli.command("token-servicio")
    @click.argument("rol", type=click.Choice([rol.value for rol in RolSistema]))
    @click.option("--horas", default=8, show_default=True, help="Validez del token.")
    def token_servicio(rol: str, horas: int) -> None:
        """Emite un token de cuenta de servicio para probar los endpoints protegidos.

        Es temporal: lo reemplaza el /login del punto I-3.1.
        """
        click.echo(emitir_token(rol.lower(), RolSistema(rol), horas))
