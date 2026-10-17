"""catálogo y consulta I-3.2

Revision ID: 9e31a2b2d101
Revises:
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa

revision = "9e31a2b2d101"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "certificacion",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("codigo", sa.String(length=50), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("activa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_certificacion")),
        sa.UniqueConstraint("codigo", name=op.f("uq_certificacion_codigo")),
    )
    op.create_table(
        "ong",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("razon_social", sa.String(length=160), nullable=False),
        sa.Column("cuit", sa.String(length=13), nullable=False),
        sa.Column("email_contacto", sa.String(length=254), nullable=True),
        sa.Column("telefono", sa.String(length=40), nullable=True),
        sa.Column(
            "estado",
            sa.Enum(
                "PENDIENTE",
                "HABILITADA",
                "SUSPENDIDA",
                name="estado_ong",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            server_default="PENDIENTE",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ong")),
        sa.UniqueConstraint("cuit", name=op.f("uq_ong_cuit")),
    )
    with op.batch_alter_table("ong", schema=None) as batch_op:
        batch_op.create_index("ix_ong_estado", ["estado"], unique=False)

    op.create_table(
        "unidad_medida",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("codigo", sa.String(length=40), nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("admite_decimales", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unidad_medida")),
        sa.UniqueConstraint("codigo", name=op.f("uq_unidad_medida_codigo")),
    )
    op.create_table(
        "ong_certificacion",
        sa.Column("ong_id", sa.BigInteger(), nullable=False),
        sa.Column("certificacion_id", sa.SmallInteger(), nullable=False),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["certificacion_id"],
            ["certificacion.id"],
            name=op.f("fk_ong_certificacion_certificacion_id_certificacion"),
        ),
        sa.ForeignKeyConstraint(
            ["ong_id"],
            ["ong.id"],
            name=op.f("fk_ong_certificacion_ong_id_ong"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "ong_id", "certificacion_id", name=op.f("pk_ong_certificacion")
        ),
    )
    op.create_table(
        "tipo_recurso",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("codigo", sa.String(length=40), nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column(
            "categoria",
            sa.Enum(
                "PERSONAL",
                "MATERIAL",
                name="categoria",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("unidad_medida_id", sa.SmallInteger(), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(
            ["unidad_medida_id"],
            ["unidad_medida.id"],
            name=op.f("fk_tipo_recurso_unidad_medida_id_unidad_medida"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tipo_recurso")),
        sa.UniqueConstraint("codigo", name=op.f("uq_tipo_recurso_codigo")),
    )
    op.create_table(
        "inventario_recurso",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ong_id", sa.BigInteger(), nullable=False),
        sa.Column("tipo_recurso_id", sa.SmallInteger(), nullable=False),
        sa.Column("cantidad_total", sa.Numeric(precision=12, scale=2), nullable=False),
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
            "cantidad_comprometida >= 0",
            name=op.f("ck_inventario_recurso_cantidad_comprometida_no_negativa"),
        ),
        sa.CheckConstraint(
            "cantidad_comprometida <= cantidad_total",
            name=op.f("ck_inventario_recurso_comprometida_no_supera_total"),
        ),
        sa.CheckConstraint(
            "cantidad_total >= 0", name=op.f("ck_inventario_recurso_cantidad_total_no_negativa")
        ),
        sa.ForeignKeyConstraint(
            ["ong_id"],
            ["ong.id"],
            name=op.f("fk_inventario_recurso_ong_id_ong"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tipo_recurso_id"],
            ["tipo_recurso.id"],
            name=op.f("fk_inventario_recurso_tipo_recurso_id_tipo_recurso"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventario_recurso")),
        sa.UniqueConstraint(
            "ong_id", "tipo_recurso_id", name=op.f("uq_inventario_recurso_ong_id_tipo_recurso_id")
        ),
    )
    with op.batch_alter_table("inventario_recurso", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_inventario_recurso_ong_id"), ["ong_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_inventario_recurso_tipo_recurso_id"),
            ["tipo_recurso_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("inventario_recurso", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_inventario_recurso_tipo_recurso_id"))
        batch_op.drop_index(batch_op.f("ix_inventario_recurso_ong_id"))
    op.drop_table("inventario_recurso")
    op.drop_table("tipo_recurso")
    op.drop_table("ong_certificacion")
    op.drop_table("unidad_medida")
    with op.batch_alter_table("ong", schema=None) as batch_op:
        batch_op.drop_index("ix_ong_estado")
    op.drop_table("ong")
    op.drop_table("certificacion")
