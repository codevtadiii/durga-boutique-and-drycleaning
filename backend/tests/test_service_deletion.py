import unittest
import uuid

from fastapi import HTTPException
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.catalog import (
    CategoryUpdate,
    ServiceUpdate,
    delete_category,
    delete_service,
    list_categories,
    list_services,
    update_category,
    update_service,
)
from app.api.orders import BookingInput, create_booking, staff_order_detail
from app.models import (
    AuditLog,
    Base,
    Customer,
    Order,
    OrderItem,
    Payment,
    PaymentAllocation,
    Service,
    ServiceCategory,
    User,
)


class ServiceDeletionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.actor = User(phone="+910000000001", account_type="staff", active=True)
        self.category = ServiceCategory(id=uuid.uuid4(), name_en="Test category", name_te="Test", active=True)
        self.service = self.make_service("Used service")
        self.db.add_all([self.actor, self.category, self.service])
        self.db.flush()

        customer_user = User(phone="+910000000002", account_type="customer", active=True)
        self.db.add(customer_user)
        self.db.flush()
        customer = Customer(user_id=customer_user.id, full_name="Test customer")
        self.db.add(customer)
        self.db.flush()
        order = Order(
            order_number="DUR-TEST-0001",
            customer_id=customer.id,
            status="order_confirmed",
            confirmed_total_paise=12500,
        )
        self.db.add(order)
        self.db.flush()
        self.order_id = order.id
        self.order_item = OrderItem(
            order_id=order.id,
            service_id=self.service.id,
            service_name_snapshot=self.service.name_en,
            unit_price_paise_snapshot=12500,
            quantity=1,
            line_total_paise=12500,
        )
        self.db.add(self.order_item)

        payment = Payment(
            customer_id=customer.id,
            recorded_by_user_id=self.actor.id,
            method="cash",
            status="successful",
            amount_paise=12500,
            idempotency_key="test-delete-payment-1",
        )
        self.db.add(payment)
        self.db.flush()
        self.payment_id = payment.id
        self.db.add(PaymentAllocation(payment_id=payment.id, order_id=order.id, amount_paise=12500))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def make_service(self, name: str) -> Service:
        return Service(
            category_id=self.category.id,
            name_en=name,
            name_te="Test service",
            description_en="",
            description_te="",
            price_paise=12500,
            quotation_required=False,
            price_is_starting=False,
            additional_charge_paise=0,
            garment_type="Test item",
            pricing_unit="per item",
            active=True,
        )

    def test_unused_service_is_permanently_deleted_and_audited(self) -> None:
        unused = self.make_service("Unused service")
        self.db.add(unused)
        self.db.commit()
        service_id = unused.id

        result = delete_service(service_id, self.db, self.actor)

        self.assertEqual(result["action"], "deleted")
        self.assertIsNone(self.db.get(Service, service_id))
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == service_id)),
            1,
        )

    def test_ordered_service_is_archived_with_history_and_financials_untouched(self) -> None:
        result = delete_service(self.service.id, self.db, self.actor)

        self.assertEqual(result["action"], "archived")
        archived = self.db.get(Service, self.service.id)
        self.assertIsNotNone(archived)
        self.assertFalse(archived.active)
        self.assertIsNotNone(archived.archived_at)

        saved_item = self.db.get(OrderItem, self.order_item.id)
        self.assertEqual(saved_item.service_id, self.service.id)
        self.assertEqual(saved_item.service_name_snapshot, "Used service")
        self.assertEqual(saved_item.unit_price_paise_snapshot, 12500)
        self.assertIsNotNone(self.db.get(Order, self.order_id))
        self.assertIsNotNone(self.db.get(Payment, self.payment_id))
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(PaymentAllocation).where(PaymentAllocation.order_id == self.order_id)),
            1,
        )
        self.assertNotIn(str(self.service.id), {row["id"] for row in list_services(self.db, self.actor)})

    def test_archived_service_cannot_be_booked(self) -> None:
        delete_service(self.service.id, self.db, self.actor)
        payload = BookingInput(
            full_name="Test customer",
            phone="9000000000",
            garments=[{"service_id": self.service.id, "garment_type": "Test item", "quantity": 1}],
        )

        with self.assertRaises(HTTPException) as raised:
            create_booking(payload, self.db)

        self.assertEqual(raised.exception.status_code, 422)

    def test_one_booking_keeps_multiple_services_quantities_and_item_details(self) -> None:
        saree_cleaning = self.make_service("Saree Dry Cleaning")
        saree_cleaning.garment_type = "Saree"
        saree_cleaning.price_paise = 16000
        saree_rolling = self.make_service("Saree Rolling")
        saree_rolling.garment_type = "Saree"
        saree_rolling.price_paise = 8000
        shirt_cleaning = self.make_service("Shirt Dry Cleaning")
        shirt_cleaning.garment_type = "Shirt"
        shirt_cleaning.price_paise = 10000
        shoe_cleaning = self.make_service("Shoe Cleaning")
        shoe_cleaning.garment_type = "Shoes"
        shoe_cleaning.price_paise = 0
        shoe_cleaning.quotation_required = True
        self.db.add_all([saree_cleaning, saree_rolling, shirt_cleaning, shoe_cleaning])
        self.db.flush()

        payload = BookingInput(
            full_name="Multi service customer",
            phone="9000000003",
            garments=[
                {
                    "service_id": saree_cleaning.id,
                    "garment_type": "Saree",
                    "quantity": 3,
                    "fabric": "Silk",
                    "colour": "Blue",
                    "condition_notes": "Small stain near the border",
                    "special_instructions": "Use low heat",
                },
                {
                    "service_id": saree_rolling.id,
                    "garment_type": "Saree",
                    "quantity": 2,
                    "fabric": "Cotton",
                    "colour": "Green",
                    "condition_notes": None,
                    "special_instructions": "Roll separately",
                },
                {
                    "service_id": shirt_cleaning.id,
                    "garment_type": "Shirt",
                    "quantity": 4,
                },
                {
                    "service_id": shoe_cleaning.id,
                    "garment_type": "Shoes",
                    "quantity": 1,
                },
            ],
        )

        created = create_booking(payload, self.db)
        order_id = self.db.scalar(select(Order.id).where(Order.order_number == created["order_number"]))
        self.assertIsNotNone(order_id)
        detail = staff_order_detail(order_id, self.db, self.actor)

        self.assertEqual(detail["order_number"], created["order_number"])
        self.assertEqual(len(detail["garments"]), 10)
        self.assertEqual(sum(garment["quantity"] for garment in detail["garments"]), 10)
        by_service = {}
        for garment in detail["garments"]:
            by_service.setdefault(garment["service_name"], []).append(garment)
        self.assertEqual(len(by_service["Saree Dry Cleaning"]), 3)
        self.assertEqual(len(by_service["Saree Rolling"]), 2)
        self.assertEqual(len(by_service["Shirt Dry Cleaning"]), 4)
        self.assertEqual(len(by_service["Shoe Cleaning"]), 1)
        self.assertTrue(all(garment["unit_price_paise"] == 16000 for garment in by_service["Saree Dry Cleaning"]))
        self.assertTrue(all(garment["line_total_paise"] == 16000 for garment in by_service["Saree Dry Cleaning"]))
        self.assertTrue(all(garment["line_total_paise"] == 8000 for garment in by_service["Saree Rolling"]))
        self.assertTrue(all(garment["line_total_paise"] == 10000 for garment in by_service["Shirt Dry Cleaning"]))
        self.assertTrue(all(garment["pricing_unit"] == "per item" for garment in by_service["Saree Rolling"]))
        self.assertEqual(by_service["Saree Dry Cleaning"][0]["fabric"], "Silk")
        self.assertEqual(by_service["Saree Dry Cleaning"][0]["condition_notes"], "Small stain near the border")
        self.assertEqual(by_service["Saree Dry Cleaning"][0]["special_instructions"], "Use low heat")
        self.assertEqual(by_service["Saree Rolling"][0]["special_instructions"], "Roll separately")
        self.assertIsNone(by_service["Shoe Cleaning"][0]["unit_price_paise"])
        self.assertIsNone(by_service["Shoe Cleaning"][0]["line_total_paise"])

    def test_archived_service_cannot_be_reenabled(self) -> None:
        delete_service(self.service.id, self.db, self.actor)

        with self.assertRaises(HTTPException) as raised:
            update_service(self.service.id, ServiceUpdate(active=True), self.db, self.actor)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertFalse(self.db.get(Service, self.service.id).active)

    def test_missing_service_returns_not_found_without_audit(self) -> None:
        missing_id = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised:
            delete_service(missing_id, self.db, self.actor)

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == missing_id)),
            0,
        )

    def test_catalogue_names_can_be_edited(self) -> None:
        result = update_category(
            self.category.id,
            CategoryUpdate(name_en="Accessories & Special Items", name_te="Updated Telugu name"),
            self.db,
            self.actor,
        )

        self.assertEqual(result["name_en"], "Accessories & Special Items")
        self.assertEqual(result["name_te"], "Updated Telugu name")
        self.assertEqual(list_categories(self.db, self.actor)[0]["name_en"], "Accessories & Special Items")

    def test_empty_catalogue_can_be_deleted(self) -> None:
        empty = ServiceCategory(name_en="Mistaken catalogue", name_te="Mistake", active=True)
        self.db.add(empty)
        self.db.commit()
        category_id = empty.id

        result = delete_category(category_id, self.db, self.actor)

        self.assertEqual(result["action"], "deleted")
        self.assertIsNone(self.db.get(ServiceCategory, category_id))
        self.assertNotIn(str(category_id), {row["id"] for row in list_categories(self.db, self.actor)})

    def test_catalogue_delete_removes_unused_services_and_archives_historical_ones(self) -> None:
        unused = self.make_service("Unused service in catalogue")
        self.db.add(unused)
        self.db.commit()
        unused_id = unused.id
        used_id = self.service.id
        category_id = self.category.id

        result = delete_category(category_id, self.db, self.actor)

        self.assertEqual(result["action"], "archived")
        self.assertEqual(result["services_deleted"], 1)
        self.assertEqual(result["services_archived"], 1)
        self.assertIsNone(self.db.get(Service, unused_id))
        archived = self.db.get(Service, used_id)
        self.assertFalse(archived.active)
        self.assertIsNotNone(archived.archived_at)
        archived_category = self.db.get(ServiceCategory, category_id)
        self.assertFalse(archived_category.active)
        self.assertIsNotNone(archived_category.archived_at)
        self.assertNotIn(str(category_id), {row["id"] for row in list_categories(self.db, self.actor)})
        saved_item = self.db.get(OrderItem, self.order_item.id)
        self.assertEqual(saved_item.service_id, used_id)
        self.assertEqual(saved_item.service_name_snapshot, "Used service")
        self.assertIsNotNone(self.db.get(Payment, self.payment_id))


if __name__ == "__main__":
    unittest.main()
