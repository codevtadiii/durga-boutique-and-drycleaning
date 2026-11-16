"""Add the default Durga service offerings without inventing prices.

Run with: python -m app.seed_catalogue
"""

from app.core.database import SessionLocal
from app.models import Service, ServiceCategory


CATALOGUE = {
    "Men": {
        "te": "పురుషులు",
        "services": [
            ("Kurta Pyjama", "కుర్తా పైజామా", "Kurta pyjama"),
            ("Sharwani", "షార్వాని", "Sharwani"),
            ("Jacket / Blazer", "జాకెట్ / బ్లేజర్", "Jacket / Blazer"),
            ("White Shirts Cleaning", "తెల్ల చొక్కాల క్లీనింగ్", "White shirt"),
            ("White Pants Cleaning", "తెల్ల ప్యాంట్ల క్లీనింగ్", "White pants"),
        ],
    },
    "Women": {
        "te": "మహిళలు",
        "services": [("Saree", "చీర", "Saree")],
    },
    "Household": {
        "te": "గృహ వస్తువులు",
        "services": [
            ("Blankets", "దుప్పట్లు", "Blanket"),
            ("Quilts", "రజాయిలు", "Quilt"),
            ("Pillows", "దిండ్లు", "Pillow"),
            ("Curtains", "కర్టెన్లు", "Curtain"),
            ("Upholstery Cleaning", "ఫర్నిచర్ వస్త్రాల క్లీనింగ్", "Upholstery"),
            ("Bed Sheets", "బెడ్ షీట్లు", "Bed sheet"),
        ],
    },
    "Kids": {
        "te": "పిల్లల దుస్తులు",
        "services": [],
    },
    "Special Services": {
        "te": "ప్రత్యేక సేవలు",
        "services": [
            ("Saree Rolling", "చీర రోలింగ్", "Saree"),
            ("Steam Pressing", "ఆవిరి ఇస్త్రీ", "Saree"),
            ("Starch Treatment", "గంజి చికిత్స", "Garment"),
        ],
    },
    "Other Services": {
        "te": "ఇతర సేవలు",
        "services": [
            ("Leather Cleaning", "లెదర్ క్లీనింగ్", "Leather item"),
            ("Suede Cleaning", "స్యూడ్ క్లీనింగ్", "Suede item"),
            ("Woollen Clothes", "ఉన్ని దుస్తులు", "Woollen garment"),
            ("Bags", "బ్యాగులు", "Bag"),
            ("Suitcases", "సూట్‌కేసులు", "Suitcase"),
            ("Shoes", "చెప్పులు", "Shoes"),
            ("Stuffed Toys", "బొమ్మలు", "Stuffed toy"),
            ("Sweaters", "స్వెటర్లు", "Sweater"),
        ],
    },
}


def seed_catalogue() -> tuple[int, int]:
    added_categories = added_services = 0
    with SessionLocal() as db:
        for category_name, definition in CATALOGUE.items():
            category = next(
                (
                    row for row in db.query(ServiceCategory).all()
                    if row.name_en.casefold() == category_name.casefold() and row.archived_at is None
                ),
                None,
            )
            if category is None:
                category = ServiceCategory(name_en=category_name, name_te=definition["te"], active=True)
                db.add(category)
                db.flush()
                added_categories += 1

            existing_names = {
                row.name_en.casefold()
                for row in db.query(Service).filter(Service.category_id == category.id).all()
            }
            for name_en, name_te, garment_type in definition["services"]:
                if name_en.casefold() in existing_names:
                    continue
                db.add(
                    Service(
                        category_id=category.id,
                        name_en=name_en,
                        name_te=name_te,
                        description_en="Staff will inspect the item and confirm the price before work begins.",
                        description_te="పని ప్రారంభించే ముందు సిబ్బంది వస్తువును పరిశీలించి ధరను నిర్ధారిస్తారు.",
                        price_paise=0,
                        quotation_required=True,
                        additional_charge_paise=0,
                        garment_type=garment_type,
                        pricing_unit="per item",
                        turnaround_days=None,
                        active=True,
                    )
                )
                added_services += 1
                existing_names.add(name_en.casefold())
        db.commit()
    return added_categories, added_services


if __name__ == "__main__":
    categories, services = seed_catalogue()
    print(f"Added {categories} categories and {services} services. Existing entries and prices were preserved.")
