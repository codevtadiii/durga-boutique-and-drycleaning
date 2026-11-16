"""Track deleted catalogues while preserving categories in order history.

Revision ID: 20261116_04
Revises: 20261116_03
Create Date: 2026-11-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20261116_04"
down_revision = "20261116_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "service_categories" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("service_categories")}
    if "archived_at" not in columns:
        op.add_column("service_categories", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("service_categories")}
    if "ix_service_categories_archived_at" not in indexes:
        op.create_index("ix_service_categories_archived_at", "service_categories", ["archived_at"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "service_categories" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("service_categories")}
    if "archived_at" in columns:
        indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("service_categories")}
        if "ix_service_categories_archived_at" in indexes:
            op.drop_index("ix_service_categories_archived_at", table_name="service_categories")
        op.drop_column("service_categories", "archived_at")
