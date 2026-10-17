"""cuentas para login y registro I-3.1

Tabla nueva `cuenta`: las cuentas de servicio (webapp, Bonita y auditor) y la cuenta que crea
cada ONG al registrarse. No cambia ninguna tabla existente.

Revision ID: 2166cf571c44
Revises: e4a7c2d9b815
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa

revision = "2166cf571c44"
down_revision = "e4a7c2d9b815"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cuenta",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("usuario", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "rol",
            sa.Enum(
                "SISTEMA_WEBAPP",
                "SISTEMA_BONITA",
                "AUDITOR",
                "ONG",
                name="rol",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("ong_id", sa.BigInteger(), nullable=True),
        sa.Column("activa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
            "(rol = 'ONG') = (ong_id IS NOT NULL)",
            name=op.f("ck_cuenta_ong_solo_en_cuentas_de_ong"),
        ),
        sa.ForeignKeyConstraint(
            ["ong_id"], ["ong.id"], name=op.f("fk_cuenta_ong_id_ong"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cuenta")),
        sa.UniqueConstraint("ong_id", name=op.f("uq_cuenta_ong_id")),
        sa.UniqueConstraint("usuario", name=op.f("uq_cuenta_usuario")),
    )


def downgrade():
    op.drop_table("cuenta")
