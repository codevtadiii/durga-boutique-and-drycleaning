"""Track prices that are advertised as starting amounts.

Revision ID: 20261116_02
Revises: 20261116_01
Create Date: 2026-11-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20261116_02"
down_revision = "20261116_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "services" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("services")}
    if "price_is_starting" not in columns:
        op.add_column("services", sa.Column("price_is_starting", sa.Boolean(), server_default=sa.false(), nullable=False))
        op.alter_column("services", "price_is_starting", server_default=None)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "services" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("services")}
    if "price_is_starting" in columns:
        op.drop_column("services", "price_is_starting")
