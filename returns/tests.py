from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from accounts.models import User
from orders.models import Order, OrderLine
from returns.serializers import ReturnRequestCreateSerializer


class ReturnValidationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(phone="07700000003", password="pass")
        self.user.is_active = True
        self.user.save()
        self.order = Order.objects.create(
            code="ORD-TEST",
            customer=self.user,
            created_by=self.user,
            status="completed",
            order_type="normal",
            delivery_method="delivery",
            items_total=Decimal("10.00"),
            grand_total=Decimal("10.00"),
            city_id=1,
            city="Baghdad",
            region_id=1,
            region="Karrada",
            location="Street 1",
        )
        self.line = OrderLine.objects.create(
            order=self.order,
            line_type="variant",
            quantity=2,
            unit_price=Decimal("5.00"),
            subtotal=Decimal("10.00"),
            product_name="Line",
        )

    def _get_serializer(self, payload):
        request = self.factory.post("/returns", payload, format="json")
        request.user = self.user
        return ReturnRequestCreateSerializer(
            data=payload, context={"request": request}
        )

    def test_rejects_quantity_over_purchased(self):
        payload = {
            "original_order_id": self.order.id,
            "resolution": "refund",
            "lines": [
                {
                    "order_line_id": self.line.id,
                    "requested_quantity": 3,
                    "reason_code": "other",
                }
            ],
        }
        serializer = self._get_serializer(payload)
        self.assertFalse(serializer.is_valid())

    def test_rejects_duplicate_order_lines(self):
        payload = {
            "original_order_id": self.order.id,
            "resolution": "refund",
            "lines": [
                {
                    "order_line_id": self.line.id,
                    "requested_quantity": 1,
                    "reason_code": "other",
                },
                {
                    "order_line_id": self.line.id,
                    "requested_quantity": 1,
                    "reason_code": "other",
                },
            ],
        }
        serializer = self._get_serializer(payload)
        self.assertFalse(serializer.is_valid())
