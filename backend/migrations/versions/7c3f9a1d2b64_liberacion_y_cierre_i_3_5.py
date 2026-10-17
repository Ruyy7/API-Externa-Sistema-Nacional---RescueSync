"""liberacion y cierre I-3.5

Revision ID: 7c3f9a1d2b64
Revises: 2166cf571c44
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa

revision = "7c3f9a1d2b64"
down_revision = "2166cf571c44"
branch_labels = None
depends_on = None


def _enum(nombre: str, *valores: str) -> sa.Enum:
    # Mismo criterio que el resto del modelo: texto con CHECK, sin ENUM nativo de PostgreSQL
    return sa.Enum(*valores, name=nombre, native_enum=False, create_constraint=True, length=30)


def _marcas_de_tiempo() -> list[sa.Column]:
    return [
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade():
    # compromiso_item: acumulado de lo liberado por actividades cumplidas. Con el CHECK de I-3.4
    # queda garantizado en la base que 0 <= liberada <= comprometida <= reservada.
    op.add_column(
        "compromiso_item",
        sa.Column(
            "cantidad_liberada",
            sa.Numeric(precision=12, scale=2),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_compromiso_item_cantidad_liberada_no_negativa"),
        "compromiso_item",
        "cantidad_liberada >= 0",
    )
    op.create_check_constraint(
        op.f("ck_compromiso_item_liberada_no_supera_comprometida"),
        "compromiso_item",
        "cantidad_liberada <= cantidad_comprometida",
    )

    # actividad: historial de liberaciones (solo inserción)
    op.create_table(
        "actividad",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("referencia", sa.String(length=100), nullable=True),
        sa.Column("compromiso_item_id", sa.BigInteger(), nullable=False),
        sa.Column("origen", _enum("origen_actividad", "INFORMADA", "CIERRE"), nullable=False),
        sa.Column("accion", _enum("accion_liberacion", "LIBERADO", "CONSUMIDO"), nullable=False),
        sa.Column("cantidad", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("fecha_cumplimiento", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column("registrada_por", sa.String(length=100), nullable=False),
        *_marcas_de_tiempo(),
        sa.CheckConstraint("cantidad > 0", name=op.f("ck_actividad_cantidad_positiva")),
        sa.CheckConstraint(
            "(origen = 'INFORMADA') = (referencia IS NOT NULL)",
            name=op.f("ck_actividad_referencia_solo_si_informada"),
        ),
        # Sin ondelete: un ítem con historial no se borra
        sa.ForeignKeyConstraint(
            ["compromiso_item_id"],
            ["compromiso_item.id"],
            name=op.f("fk_actividad_compromiso_item_id_compromiso_item"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actividad")),
        sa.UniqueConstraint("referencia", name=op.f("uq_actividad_referencia")),
    )
    op.create_index(op.f("ix_actividad_compromiso_item_id"), "actividad", ["compromiso_item_id"])

    # cierre_proyecto: un cierre por emergencia
    op.create_table(
        "cierre_proyecto",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("emergencia_referencia", sa.String(length=100), nullable=False),
        sa.Column("fecha_cierre", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column("cerrado_por", sa.String(length=100), nullable=False),
        *_marcas_de_tiempo(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cierre_proyecto")),
        sa.UniqueConstraint(
            "emergencia_referencia", name=op.f("uq_cierre_proyecto_emergencia_referencia")
        ),
    )


def downgrade():
    op.drop_table("cierre_proyecto")

    op.drop_index(op.f("ix_actividad_compromiso_item_id"), table_name="actividad")
    op.drop_table("actividad")

    op.drop_constraint(
        op.f("ck_compromiso_item_liberada_no_supera_comprometida"),
        "compromiso_item",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_compromiso_item_cantidad_liberada_no_negativa"),
        "compromiso_item",
        type_="check",
    )
    op.drop_column("compromiso_item", "cantidad_liberada")
