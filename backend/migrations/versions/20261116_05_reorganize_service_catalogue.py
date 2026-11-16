"""Group the catalogue into customer-friendly service sections.

Revision ID: 20261116_05
Revises: 20261116_04
Create Date: 2026-11-16
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "20261116_05"
down_revision = "20261116_04"
branch_labels = None
depends_on = None


CATALOGUES = (
    ("Men", "పురుషులు"),
    ("Women", "మహిళలు"),
    ("Household", "గృహ వస్తువులు"),
    ("Kids", "పిల్లల దుస్తులు"),
    ("Special Services", "ప్రత్యేక సేవలు"),
    ("Other Services", "ఇతర సేవలు"),
)

WOMEN_SERVICES = {
    "blouse", "crop top lehenga", "dupatha", "frock", "kurtha", "lehenga", "punjabi dress", "saree",
}
MEN_SERVICES = {
    "jacket / blazer", "kurta pyjama", "lungi / pancha", "pant", "pyjama", "r-made dhothi",
    "sharwani", "sherwani", "shirt", "white pants cleaning", "white shirts cleaning",
}
HOUSEHOLD_SERVICES = {
    "bed sheet", "bed sheets", "bedsheet", "bedsheets", "blankets", "curtains", "pillows", "quilts",
    "upholstery cleaning",
}
SPECIAL_SERVICES = {
    "chemical wash pant", "chemical wash shirt", "chemical wash lungi / pancha", "chemical wash khanduwa",
    "khanduwa", "saree rolling", "steam pressing", "starch treatment", "dying", "dyeing",
}
KIDS_CATEGORY_NAMES = {"kids' clothing services", "kids clothing services", "kids"}
SPECIAL_CATEGORY_NAMES = {"chemical wash services", "saree care", "saree services", "special services"}
HOUSEHOLD_CATEGORY_NAMES = {"household"}


def _target_catalogue(service_name: str, source_category: str) -> str:
    name = service_name.casefold().strip()
    source = source_category.casefold().strip()
    if source in KIDS_CATEGORY_NAMES or name.startswith("kids "):
        return "Kids"
    if source in SPECIAL_CATEGORY_NAMES or name in SPECIAL_SERVICES or name.startswith("chemical wash"):
        return "Special Services"
    if source in HOUSEHOLD_CATEGORY_NAMES or name in HOUSEHOLD_SERVICES:
        return "Household"
    if name in WOMEN_SERVICES:
        return "Women"
    if name in MEN_SERVICES:
        return "Men"
    return "Other Services"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "services" not in inspector.get_table_names() or "service_categories" not in inspector.get_table_names():
        return

    metadata = sa.MetaData()
    categories = sa.Table("service_categories", metadata, autoload_with=connection)
    services = sa.Table("services", metadata, autoload_with=connection)
    category_rows = list(connection.execute(sa.select(categories)).mappings())

    canonical_ids = {}
    for english_name, telugu_name in CATALOGUES:
        existing = next(
            (
                row for row in category_rows
                if row["name_en"].casefold() == english_name.casefold() and row["archived_at"] is None
            ),
            None,
        )
        if existing is None:
            category_id = uuid.uuid4()
            connection.execute(sa.insert(categories).values(
                id=category_id,
                name_en=english_name,
                name_te=telugu_name,
                active=True,
                archived_at=None,
            ))
            canonical_ids[english_name] = category_id
        else:
            canonical_ids[english_name] = existing["id"]
            connection.execute(
                sa.update(categories).where(categories.c.id == existing["id"]).values(active=True)
            )

    category_names = {row["id"]: row["name_en"] for row in category_rows}
    service_rows = list(connection.execute(sa.select(services)).mappings())
    for service in service_rows:
        source_name = category_names.get(service["category_id"], "")
        target_name = _target_catalogue(service["name_en"], source_name)
        connection.execute(
            sa.update(services)
            .where(services.c.id == service["id"])
            .values(category_id=canonical_ids[target_name])
        )

    for row in category_rows:
        if row["id"] not in canonical_ids.values():
            connection.execute(
                sa.update(categories)
                .where(categories.c.id == row["id"])
                .values(active=False, archived_at=sa.func.coalesce(categories.c.archived_at, sa.func.now()))
            )

    existing_names = {row["name_en"].casefold().strip() for row in service_rows}
    for name, telugu_name, category_name, garment_type in (
        ("Bed Sheets", "బెడ్ షీట్లు", "Household", "Bed sheet"),
        ("Sweaters", "స్వెటర్లు", "Other Services", "Sweater"),
    ):
        if name.casefold() in existing_names:
            continue
        connection.execute(sa.insert(services).values(
            id=uuid.uuid4(),
            category_id=canonical_ids[category_name],
            name_en=name,
            name_te=telugu_name,
            description_en="Staff will inspect the item and confirm the price before work begins.",
            description_te="",
            price_paise=0,
            quotation_required=True,
            price_is_starting=False,
            additional_charge_paise=0,
            garment_type=garment_type,
            pricing_unit="per item",
            turnaround_days=None,
            active=True,
            archived_at=None,
        ))
        existing_names.add(name.casefold())


def downgrade() -> None:
    # Keep the revised grouping in place; reverting would alter staff catalogue edits made after upgrade.
    pass
