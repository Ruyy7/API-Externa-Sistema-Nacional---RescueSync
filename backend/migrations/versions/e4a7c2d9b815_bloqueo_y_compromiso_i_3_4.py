"""bloqueo y compromiso I-3.4

Revision ID: e4a7c2d9b815
Revises: b71c3d9f4a20
Create Date: 2026-10-11
"""

from alembic import op
import sqlalchemy as sa

revision = "e4a7c2d9b815"
down_revision = "b71c3d9f4a20"
branch_labels = None
depends_on = None


_CHECKS_DE_COMPROMISO = {
    "ck_compromiso_confirmado_con_fecha": (
        "estado NOT IN ('COMPROMETIDO', 'FINALIZADO') OR confirmado_en IS NOT NULL"
    ),
    "ck_compromiso_cancelado_con_fecha": "estado <> 'CANCELADO' OR cancelado_en IS NOT NULL",
    "ck_compromiso_vencido_con_fecha": "estado <> 'VENCIDO' OR vencido_en IS NOT NULL",
    "ck_compromiso_finalizado_con_fecha": ("estado <> 'FINALIZADO' OR finalizado_en IS NOT NULL"),
}
_FECHAS_DE_TRANSICION = ("confirmado_en", "cancelado_en", "vencido_en", "finalizado_en")


def upgrade():
    # compromiso: quién lo creó y cuándo cambió de estado
    op.add_column(
        "compromiso",
        sa.Column(
            "creado_por", sa.String(length=100), nullable=False, server_default="desconocido"
        ),
    )
    op.alter_column("compromiso", "creado_por", server_default=None)
    for columna in _FECHAS_DE_TRANSICION:
        op.add_column("compromiso", sa.Column(columna, sa.DateTime(timezone=True), nullable=True))
    for nombre, condicion in _CHECKS_DE_COMPROMISO.items():
        op.create_check_constraint(op.f(nombre), "compromiso", condicion)
    op.create_unique_constraint(op.f("uq_compromiso_id_ong_id"), "compromiso", ["id", "ong_id"])
    op.create_index(
        "ix_compromiso_reservados",
        "compromiso",
        ["convocatoria_id"],
        postgresql_where=sa.text("estado = 'RESERVADO'"),
    )

    # convocatoria: a qué emergencia pertenece (la liberación de I-3.5 busca por emergencia)
    op.add_column(
        "convocatoria",
        sa.Column(
            "emergencia_referencia",
            sa.String(length=100),
            nullable=False,
            server_default="desconocida",
        ),
    )
    op.alter_column("convocatoria", "emergencia_referencia", server_default=None)
    op.create_index(
        op.f("ix_convocatoria_emergencia_referencia"), "convocatoria", ["emergencia_referencia"]
    )

    op.create_unique_constraint(
        op.f("uq_inventario_recurso_id_ong_id"), "inventario_recurso", ["id", "ong_id"]
    )

    # compromiso_item: ong_id redundante para que la base garantice que el recurso reservado es de
    # la misma ONG del compromiso (dos FK compuestas)
    op.add_column("compromiso_item", sa.Column("ong_id", sa.BigInteger(), nullable=True))
    op.execute(
        "UPDATE compromiso_item AS ci SET ong_id = c.ong_id "
        "FROM compromiso AS c WHERE c.id = ci.compromiso_id"
    )
    op.alter_column("compromiso_item", "ong_id", nullable=False)
    op.drop_constraint(
        op.f("fk_compromiso_item_compromiso_id_compromiso"), "compromiso_item", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_compromiso_item_inventario_recurso_id_inventario_recurso"),
        "compromiso_item",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_compromiso_item_compromiso_ong"),
        "compromiso_item",
        "compromiso",
        ["compromiso_id", "ong_id"],
        ["id", "ong_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_compromiso_item_inventario_ong"),
        "compromiso_item",
        "inventario_recurso",
        ["inventario_recurso_id", "ong_id"],
        ["id", "ong_id"],
    )
    op.create_check_constraint(
        op.f("ck_compromiso_item_comprometida_no_supera_reservada"),
        "compromiso_item",
        "cantidad_comprometida <= cantidad_reservada",
    )


def downgrade():
    op.drop_constraint(
        op.f("ck_compromiso_item_comprometida_no_supera_reservada"),
        "compromiso_item",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_compromiso_item_inventario_ong"), "compromiso_item", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_compromiso_item_compromiso_ong"), "compromiso_item", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("fk_compromiso_item_compromiso_id_compromiso"),
        "compromiso_item",
        "compromiso",
        ["compromiso_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_compromiso_item_inventario_recurso_id_inventario_recurso"),
        "compromiso_item",
        "inventario_recurso",
        ["inventario_recurso_id"],
        ["id"],
    )
    op.drop_column("compromiso_item", "ong_id")

    op.drop_constraint(
        op.f("uq_inventario_recurso_id_ong_id"), "inventario_recurso", type_="unique"
    )

    op.drop_index(op.f("ix_convocatoria_emergencia_referencia"), table_name="convocatoria")
    op.drop_column("convocatoria", "emergencia_referencia")

    op.drop_index("ix_compromiso_reservados", table_name="compromiso")
    op.drop_constraint(op.f("uq_compromiso_id_ong_id"), "compromiso", type_="unique")
    for nombre in _CHECKS_DE_COMPROMISO:
        op.drop_constraint(op.f(nombre), "compromiso", type_="check")
    for columna in (*reversed(_FECHAS_DE_TRANSICION), "creado_por"):
        op.drop_column("compromiso", columna)
