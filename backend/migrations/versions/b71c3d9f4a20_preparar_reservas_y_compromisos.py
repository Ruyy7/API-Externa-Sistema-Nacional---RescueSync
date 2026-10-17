"""preparar reservas y compromisos

Revision ID: b71c3d9f4a20
Revises: 9e31a2b2d101
Create Date: 2026-10-11
"""

from alembic import op
import sqlalchemy as sa

revision = "b71c3d9f4a20"
down_revision = "9e31a2b2d101"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tipo_recurso",
        sa.Column(
            "reutilizable",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Indica si el recurso vuelve al stock al finalizar la actividad",
        ),
    )
    op.add_column(
        "inventario_recurso",
        sa.Column(
            "cantidad_bloqueada",
            sa.Numeric(precision=12, scale=2),
            server_default="0",
            nullable=False,
        ),
    )
    with op.batch_alter_table("inventario_recurso", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("ck_inventario_recurso_comprometida_no_supera_total"),
            type_="check",
        )
        batch_op.create_check_constraint(
            "cantidad_bloqueada_no_negativa", "cantidad_bloqueada >= 0"
        )
        batch_op.create_check_constraint(
            "reservada_y_comprometida_no_superan_total",
            "cantidad_bloqueada + cantidad_comprometida <= cantidad_total",
        )

    op.create_table(
        "convocatoria",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("referencia", sa.String(length=100), nullable=False),
        sa.Column("fecha_cierre", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_limite_adjudicacion", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fecha_limite_adjudicacion >= fecha_cierre",
            name=op.f("ck_convocatoria_limite_adjudicacion_no_antes_del_cierre"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_convocatoria")),
        sa.UniqueConstraint("referencia", name=op.f("uq_convocatoria_referencia")),
    )
    op.create_table(
        "compromiso",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("convocatoria_id", sa.BigInteger(), nullable=False),
        sa.Column("ong_id", sa.BigInteger(), nullable=False),
        sa.Column("oferta_referencia", sa.String(length=100), nullable=False),
        sa.Column(
            "estado",
            sa.Enum(
                "RESERVADO",
                "COMPROMETIDO",
                "FINALIZADO",
                "CANCELADO",
                "VENCIDO",
                name="estado_compromiso",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            server_default="RESERVADO",
            nullable=False,
        ),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["convocatoria_id"],
            ["convocatoria.id"],
            name=op.f("fk_compromiso_convocatoria_id_convocatoria"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ong_id"], ["ong.id"], name=op.f("fk_compromiso_ong_id_ong")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_compromiso")),
        sa.UniqueConstraint(
            "oferta_referencia", "ong_id", name=op.f("uq_compromiso_oferta_referencia_ong_id")
        ),
    )
    with op.batch_alter_table("compromiso", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_compromiso_convocatoria_id"), ["convocatoria_id"])
        batch_op.create_index(batch_op.f("ix_compromiso_ong_id"), ["ong_id"])

    op.create_table(
        "compromiso_item",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("compromiso_id", sa.BigInteger(), nullable=False),
        sa.Column("inventario_recurso_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "cantidad_reservada",
            sa.Numeric(precision=12, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "cantidad_comprometida",
            sa.Numeric(precision=12, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cantidad_reservada >= 0",
            name=op.f("ck_compromiso_item_cantidad_reservada_no_negativa"),
        ),
        sa.CheckConstraint(
            "cantidad_comprometida >= 0",
            name=op.f("ck_compromiso_item_cantidad_comprometida_no_negativa"),
        ),
        sa.CheckConstraint(
            "cantidad_reservada + cantidad_comprometida > 0",
            name=op.f("ck_compromiso_item_item_con_cantidad_positiva"),
        ),
        sa.ForeignKeyConstraint(
            ["compromiso_id"],
            ["compromiso.id"],
            name=op.f("fk_compromiso_item_compromiso_id_compromiso"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["inventario_recurso_id"],
            ["inventario_recurso.id"],
            name=op.f("fk_compromiso_item_inventario_recurso_id_inventario_recurso"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_compromiso_item")),
        sa.UniqueConstraint(
            "compromiso_id",
            "inventario_recurso_id",
            name=op.f("uq_compromiso_item_compromiso_id_inventario_recurso_id"),
        ),
    )
    with op.batch_alter_table("compromiso_item", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_compromiso_item_compromiso_id"), ["compromiso_id"])
        batch_op.create_index(
            batch_op.f("ix_compromiso_item_inventario_recurso_id"), ["inventario_recurso_id"]
        )


def downgrade():
    with op.batch_alter_table("compromiso_item", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_compromiso_item_inventario_recurso_id"))
        batch_op.drop_index(batch_op.f("ix_compromiso_item_compromiso_id"))
    op.drop_table("compromiso_item")

    with op.batch_alter_table("compromiso", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_compromiso_ong_id"))
        batch_op.drop_index(batch_op.f("ix_compromiso_convocatoria_id"))
    op.drop_table("compromiso")
    op.drop_table("convocatoria")

    with op.batch_alter_table("inventario_recurso", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f(
                "ck_inventario_recurso_reservada_y_comprometida_no_superan_total"
            ),
            type_="check",
        )
        batch_op.drop_constraint(
            batch_op.f("ck_inventario_recurso_cantidad_bloqueada_no_negativa"),
            type_="check",
        )
        batch_op.create_check_constraint(
            "comprometida_no_supera_total", "cantidad_comprometida <= cantidad_total"
        )
    op.drop_column("inventario_recurso", "cantidad_bloqueada")
    op.drop_column("tipo_recurso", "reutilizable")
