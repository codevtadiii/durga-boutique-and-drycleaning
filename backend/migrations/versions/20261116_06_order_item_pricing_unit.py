"""Snapshot the catalogue pricing unit on each order item."""

from alembic import op
import sqlalchemy as sa


revision = "20261116_06"
down_revision = "20261116_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "order_items" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("order_items")}
    if "pricing_unit_snapshot" in columns:
        return

    op.add_column(
        "order_items",
        sa.Column("pricing_unit_snapshot", sa.String(length=30), server_default="per item", nullable=False),
    )
    if "services" in inspector.get_table_names():
        op.execute(
            "UPDATE order_items "
            "SET pricing_unit_snapshot = COALESCE(("
            "SELECT services.pricing_unit FROM services WHERE services.id = order_items.service_id"
            "), 'per item')"
        )
    op.alter_column("order_items", "pricing_unit_snapshot", server_default=None)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "order_items" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("order_items")}
    if "pricing_unit_snapshot" in columns:
        op.drop_column("order_items", "pricing_unit_snapshot")
