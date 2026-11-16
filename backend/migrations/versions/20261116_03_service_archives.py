"""Mark services archived after historical use.

Revision ID: 20261116_03
Revises: 20261116_02
Create Date: 2026-11-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20261116_03"
down_revision = "20261116_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "services" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("services")}
    if "archived_at" not in columns:
        op.add_column("services", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("services")}
    if "ix_services_archived_at" not in indexes:
        op.create_index("ix_services_archived_at", "services", ["archived_at"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "services" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("services")}
    if "archived_at" in columns:
        indexes = {index["name"] for index in inspector.get_indexes("services")}
        if "ix_services_archived_at" in indexes:
            op.drop_index("ix_services_archived_at", table_name="services")
        op.drop_column("services", "archived_at")
