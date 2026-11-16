"""Add quote-aware service catalogue fields.

Revision ID: 20261116_01
Revises:
Create Date: 2026-11-16

This is an additive migration for databases whose tables were created by the
existing AUTO_CREATE_SCHEMA path. It is also safe after create_all has already
created the new columns.
"""

from alembic import op
import sqlalchemy as sa

revision = "20261116_01"
down_revision = None
branch_labels = None
depends_on = None


def _service_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "services" not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns("services")}


def upgrade() -> None:
    columns = _service_columns()
    if not columns:
        # A fresh Compose database gets its tables from AUTO_CREATE_SCHEMA.
        # Keep this migration a no-op when the services table is not present.
        return
    if "garment_type" not in columns:
        op.add_column("services", sa.Column("garment_type", sa.String(length=100), nullable=True))
    if "quotation_required" not in columns:
        op.add_column(
            "services",
            sa.Column("quotation_required", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
        op.alter_column("services", "quotation_required", server_default=None)
    if "additional_charge_paise" not in columns:
        op.add_column(
            "services",
            sa.Column("additional_charge_paise", sa.Integer(), server_default="0", nullable=False),
        )
        op.alter_column("services", "additional_charge_paise", server_default=None)


def downgrade() -> None:
    columns = _service_columns()
    for name in ("additional_charge_paise", "quotation_required", "garment_type"):
        if name in columns:
            op.drop_column("services", name)
