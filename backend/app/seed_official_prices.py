"""Import the business-provided price list without altering existing orders.

Run once with: python -m app.seed_official_prices
"""

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import AuditLog, Service, ServiceCategory


# category, category Telugu, supplied display name, Telugu name, item type,
# rupees, is a starting amount. Names with uncertain spelling are kept exactly
# as supplied by the business owner.
OFFICIAL_PRICE_LIST = [
    ('Men', 'పురుషులు', 'Pant', 'ప్యాంట్', 'Pant', 100, False),
    ('Men', 'పురుషులు', 'Shirt', 'షర్ట్', 'Shirt', 100, True),
    ('Men', 'పురుషులు', 'Jacket / Blazer', 'జాకెట్ / బ్లేజర్', 'Jacket / Blazer', 350, False),
    ('Men', 'పురుషులు', 'Sharwani', 'షార్వాని', 'Sharwani', 500, True),
    ('Men', 'పురుషులు', 'Lungi / Pancha', 'లుంగీ / పంచ', 'Lungi / Pancha', 150, False),
    ('Men', 'పురుషులు', 'R-made Dhothi', 'R-made Dhothi', 'R-made Dhothi', 200, False),
    ('Women', 'మహిళలు', 'Kurtha', 'కుర్థా', 'Kurtha', 150, True),
    ('Men', 'పురుషులు', 'Pyjama', 'పైజామా', 'Pyjama', 100, False),
    ('Women', 'మహిళలు', 'Crop Top Lehenga', 'క్రాప్ టాప్ లెహంగా', 'Crop Top Lehenga', 350, True),
    ('Women', 'మహిళలు', 'Lehenga', 'లెహంగా', 'Lehenga', 250, False),
    ('Women', 'మహిళలు', 'Dupatha', 'దుపట్టా', 'Dupatha', 100, False),
    ('Women', 'మహిళలు', 'Blouse', 'బ్లౌజ్', 'Blouse', 50, True),
    ('Women', 'మహిళలు', 'Saree', 'చీర', 'Saree', 160, True),
    ('Women', 'మహిళలు', 'Frock', 'ఫ్రాక్', 'Frock', 300, False),
    ('Women', 'మహిళలు', 'Punjabi Dress', 'పంజాబీ డ్రెస్', 'Punjabi Dress', 300, False),
    ('Special Services', 'ప్రత్యేక సేవలు', 'Chemical wash Shirt', 'షర్ట్', 'Shirt', 250, False),
    ('Special Services', 'ప్రత్యేక సేవలు', 'Chemical Wash Pant', 'ప్యాంట్', 'Pant', 250, False),
    ('Special Services', 'ప్రత్యేక సేవలు', 'Lungi / Pancha', 'లుంగీ / పంచ', 'Lungi / Pancha', 250, False),
    ('Special Services', 'ప్రత్యేక సేవలు', 'Khanduwa', 'ఖండువా', 'Khanduwa', 250, False),
    ('Special Services', 'ప్రత్యేక సేవలు', 'Saree Rolling', 'చీర రోలింగ్', 'Saree', 80, False),
    ('Kids', 'పిల్లల దుస్తులు', 'Kids Pyjama', 'పిల్లల పైజామా', 'Kids Pyjama', 100, False),
    ('Kids', 'పిల్లల దుస్తులు', 'Kids Kurtha', 'పిల్లల కుర్థా', 'Kids Kurtha', 100, False),
    ('Kids', 'పిల్లల దుస్తులు', 'Kids Lehenga 2pc', 'పిల్లల లెహంగా 2pc', 'Kids Lehenga 2pc', 300, True),
    ('Kids', 'పిల్లల దుస్తులు', 'Kids Kurta C.W', 'Kids Kurta C.W', 'Kids Kurta C.W', 250, False),
]

LEGACY_SERVICE_MATCHES = {
    ("Women", "Saree"): ("Saree Care", "Dry Cleaning"),
    ("Special Services", "Saree Rolling"): ("Saree Care", "Rolling"),
    ("Men", "Jacket / Blazer"): ("Traditional & Formal", "Blazers"),
}


def _find_category(db, name: str) -> ServiceCategory | None:
    return next((
        row for row in db.scalars(select(ServiceCategory).where(ServiceCategory.archived_at.is_(None)))
        if row.name_en.casefold() == name.casefold()
    ), None)


def _find_service(db, category_id, name: str) -> Service | None:
    return next(
        (row for row in db.scalars(select(Service).where(Service.category_id == category_id)) if row.name_en.casefold() == name.casefold()),
        None,
    )


def _order_reference_count(db, service: Service) -> int:
    from app.models import OrderItem

    return int(db.scalar(select(func.count()).select_from(OrderItem).where(OrderItem.service_id == service.id)) or 0)


def _audit_reconciliation(db, service: Service, action: str, before: dict) -> None:
    db.add(AuditLog(
        action=action,
        entity_type="service",
        entity_id=service.id,
        before_after_summary={
            "before": before,
            "after": {
                "category_id": str(service.category_id),
                "name_en": service.name_en,
                "price_paise": service.price_paise,
                "quotation_required": service.quotation_required,
                "price_is_starting": service.price_is_starting,
                "active": service.active,
            },
        },
    ))


def seed_official_prices() -> dict[str, int]:
    counts = {"categories_added": 0, "services_added": 0, "seed_services_updated": 0, "existing_prices_preserved": 0}
    with SessionLocal() as db:
        categories: dict[str, ServiceCategory] = {}
        for category_name, category_te, *_ in OFFICIAL_PRICE_LIST:
            if category_name.casefold() in categories:
                continue
            category = _find_category(db, category_name)
            if category is None:
                category = ServiceCategory(name_en=category_name, name_te=category_te, active=True)
                db.add(category)
                db.flush()
                counts["categories_added"] += 1
            categories[category_name.casefold()] = category

        for category_name, _category_te, name, name_te, garment_type, rupees, is_starting in OFFICIAL_PRICE_LIST:
            category = categories[category_name.casefold()]
            service = _find_service(db, category.id, name)
            legacy_before = None
            if name == "Saree":
                legacy_saree = next(
                    (row for row in db.scalars(select(Service)) if row.name_en.casefold() == "dry cleaning(saree)" and row.active),
                    None,
                )
                if legacy_saree is not None and legacy_saree is not service:
                    legacy_refs = _order_reference_count(db, legacy_saree)
                    official_refs = _order_reference_count(db, service) if service else 0
                    if legacy_refs > 0 and official_refs > 0:
                        legacy_saree.active = False
                        _audit_reconciliation(db, legacy_saree, "service.duplicate_archived", {
                            "name_en": legacy_saree.name_en,
                            "price_paise": legacy_saree.price_paise,
                            "order_references": legacy_refs,
                        })
                        counts["existing_prices_preserved"] += 1
                    else:
                        keep_legacy = legacy_refs > 0 or official_refs == 0
                        if keep_legacy:
                            if service is not None:
                                db.delete(service)
                            service = legacy_saree
                            legacy_before = {
                                "category_id": str(service.category_id),
                                "name_en": service.name_en,
                                "price_paise": service.price_paise,
                                "quotation_required": service.quotation_required,
                                "price_is_starting": service.price_is_starting,
                            }
                        else:
                            db.delete(legacy_saree)
                            counts["existing_prices_preserved"] += 1
            legacy_match = LEGACY_SERVICE_MATCHES.get((category_name, name))
            if service is None and legacy_match:
                legacy_category_name, legacy_service_name = legacy_match
                legacy_category = _find_category(db, legacy_category_name)
                legacy_service = _find_service(db, legacy_category.id, legacy_service_name) if legacy_category else None
                if legacy_service is not None:
                    service = legacy_service
                    legacy_before = {
                        "category_id": str(service.category_id),
                        "name_en": service.name_en,
                        "price_paise": service.price_paise,
                        "quotation_required": service.quotation_required,
                        "price_is_starting": service.price_is_starting,
                    }
                    service.category_id = category.id
                    service.name_en = name
                    service.name_te = name_te
                    service.garment_type = garment_type

            amount_paise = rupees * 100 if rupees is not None else 0
            quote_required = is_starting or rupees is None
            if service is None:
                service = Service(
                    category_id=category.id,
                    name_en=name,
                    name_te=name_te,
                    description_en="Starting price; staff confirms the final amount after checking the item." if is_starting else "",
                    description_te="",
                    price_paise=amount_paise,
                    quotation_required=quote_required,
                    price_is_starting=is_starting,
                    additional_charge_paise=0,
                    garment_type=garment_type,
                    pricing_unit="per item",
                    turnaround_days=None,
                    active=True,
                )
                db.add(service)
                counts["services_added"] += 1
                continue

            if legacy_before is not None or (service.price_paise == 0 and service.quotation_required):
                before = legacy_before or {
                    "category_id": str(service.category_id),
                    "name_en": service.name_en,
                    "price_paise": service.price_paise,
                    "quotation_required": service.quotation_required,
                    "price_is_starting": service.price_is_starting,
                }
                service.category_id = category.id
                service.name_en = name
                service.name_te = name_te
                service.garment_type = garment_type
                service.price_paise = amount_paise
                service.quotation_required = quote_required
                service.price_is_starting = is_starting
                service.additional_charge_paise = 0
                service.pricing_unit = "per item"
                if is_starting:
                    service.description_en = "Starting price; staff confirms the final amount after checking the item."
                _audit_reconciliation(db, service, "service.official_price_list_imported", before)
                counts["seed_services_updated"] += 1
            else:
                # Do not overwrite prices already configured by the business.
                counts["existing_prices_preserved"] += 1
                if legacy_before is not None:
                    db.add(AuditLog(
                        action="service.official_name_mapped",
                        entity_type="service",
                        entity_id=service.id,
                        before_after_summary={
                            "before": legacy_before,
                            "after": {
                                "category_id": str(service.category_id),
                                "name_en": service.name_en,
                                "price_paise": service.price_paise,
                                "quotation_required": service.quotation_required,
                                "price_is_starting": service.price_is_starting,
                            },
                            "note": "The business-configured price was preserved.",
                        },
                    ))

        db.commit()
    return counts


if __name__ == "__main__":
    print(seed_official_prices())
