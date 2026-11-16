import unittest
import uuid

from pydantic import ValidationError

from app.api.catalog import ServiceInput, _service_view
from app.api.orders import _public_service_price
from app.core.security import password_hash, verify_pin
from app.models import Service, ServiceCategory
from app.seed_catalogue import CATALOGUE
from app.seed_official_prices import OFFICIAL_PRICE_LIST


class CatalogueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base_input = {
            "category_id": uuid.uuid4(),
            "name_en": "Test service",
            "name_te": "పరీక్ష సేవ",
            "pricing_unit": "per item",
        }

    def test_quote_required_service_can_be_created_without_a_price(self) -> None:
        service = ServiceInput(**self.base_input, quotation_required=True)
        self.assertIsNone(service.price_paise)

    def test_fixed_service_requires_a_positive_configured_price(self) -> None:
        service = ServiceInput(**self.base_input, quotation_required=False, price_paise=12500)
        self.assertEqual(service.price_paise, 12500)
        with self.assertRaises(ValidationError):
            ServiceInput(**self.base_input, quotation_required=False)
        with self.assertRaises(ValidationError):
            ServiceInput(**self.base_input, quotation_required=False, price_paise=0)

    def test_starting_price_requires_staff_confirmation_and_an_amount(self) -> None:
        service = ServiceInput(**self.base_input, price_paise=10000, quotation_required=True, price_is_starting=True)
        self.assertTrue(service.price_is_starting)
        with self.assertRaises(ValidationError):
            ServiceInput(**self.base_input, price_paise=10000, quotation_required=False, price_is_starting=True)
        with self.assertRaises(ValidationError):
            ServiceInput(**self.base_input, quotation_required=True, price_is_starting=True)

    def test_quote_price_is_never_exposed_as_zero(self) -> None:
        service = Service(
            id=uuid.uuid4(),
            category_id=uuid.uuid4(),
            name_en="Variable service",
            name_te="వేరియబుల్ సేవ",
            description_en="",
            description_te="",
            price_paise=0,
            quotation_required=True,
            additional_charge_paise=0,
            pricing_unit="per item",
            active=True,
            category=ServiceCategory(id=uuid.uuid4(), name_en="Test category", name_te="Test", active=True),
        )
        view = _service_view(service)
        self.assertEqual(view["price_paise"], 0)
        self.assertTrue(view["quotation_required"])
        self.assertIsNone(_public_service_price(service))

    def test_starting_amount_is_public_but_zero_placeholder_is_not(self) -> None:
        service = Service(price_paise=16000, quotation_required=True, price_is_starting=True)
        self.assertEqual(_public_service_price(service), 16000)

    def test_seed_catalogue_uses_the_six_customer_facing_groups(self) -> None:
        services = [service for category in CATALOGUE.values() for service in category["services"]]
        self.assertEqual(len(CATALOGUE), 6)
        self.assertEqual(len(services), 23)
        self.assertTrue(all(len(service) == 3 for service in services))
        self.assertEqual(
            set(CATALOGUE),
            {"Men", "Women", "Household", "Kids", "Special Services", "Other Services"},
        )

    def test_official_price_list_preserves_unclear_supplied_names(self) -> None:
        self.assertEqual(len(OFFICIAL_PRICE_LIST), 24)
        names = {row[2] for row in OFFICIAL_PRICE_LIST}
        self.assertIn("Sharwani", names)
        self.assertIn("R-made Dhothi", names)
        self.assertIn("Khanduwa", names)
        self.assertTrue(all(row[0] in {"Men", "Women", "Household", "Kids", "Special Services", "Other Services"} for row in OFFICIAL_PRICE_LIST))
        saree = next(row for row in OFFICIAL_PRICE_LIST if row[2] == "Saree")
        rolling = next(row for row in OFFICIAL_PRICE_LIST if row[2] == "Saree Rolling")
        self.assertEqual(saree[5:7], (160, True))
        self.assertEqual(rolling[5:7], (80, False))


class PinVerificationTests(unittest.TestCase):
    def test_pwdlib_pin_hash_accepts_correct_pin_and_rejects_other_or_unknown_hash(self) -> None:
        digest = password_hash.hash("482915")
        self.assertTrue(verify_pin("482915", digest))
        self.assertFalse(verify_pin("111111", digest))
        self.assertFalse(verify_pin("482915", "unrecognized-hash"))


if __name__ == "__main__":
    unittest.main()
