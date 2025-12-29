from decimal import Decimal
from django.test import TestCase
from accounts.models import User, ShippingAddress
from carts.models import Cart, CartItem
from catalog.models import Product, ProductVariant, Bundle, BundleItem
from orders.services import OrderService


class OrderServiceTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(phone="07700000002", password="pass")
        self.customer.is_active = True
        self.customer.save()
        self.staff = User.objects.create_user(
            phone="07700000099", password="pass", role="employee", is_staff=True
        )
        self.staff.save()
        self.product = Product.objects.create(name="Order Product")
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Variant",
            sale_price=Decimal("15.00"),
            cost_price=Decimal("8.00"),
            wholesale_price=Decimal("10.00"),
            stock=5,
            sku="SKU-ORD",
            barcode="BAR-ORD",
        )

    def _build_cart(self, qty=1, unit_price=Decimal("15.00"), variant_stock=None):
        if variant_stock is not None:
            self.variant.stock = variant_stock
            self.variant.save(update_fields=["stock"])
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(
            cart=cart,
            line_type="variant",
            variant=self.variant,
            quantity=qty,
            unit_price=unit_price,
        )
        return cart

    def test_create_from_cart_updates_stock_and_shipping_snapshot(self):
        cart = self._build_cart(qty=2)
        shipping_data = {
            "full_name": "Test User",
            "city_id": 1,
            "city": "Baghdad",
            "region_id": 2,
            "region": "Karrada",
            "location": "Street 1",
        }
        order = OrderService.create_from_cart(
            cart=cart,
            created_by=self.customer,
            shipping_data=shipping_data,
        )
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 3)
        self.assertEqual(order.city_id, 1)
        self.assertEqual(order.region_id, 2)
        self.assertEqual(order.items_total, Decimal("30.00"))
        self.assertEqual(order.grand_total, Decimal("30.00"))

    def test_create_from_cart_blocks_insufficient_stock(self):
        cart = self._build_cart(qty=2, variant_stock=2)
        # exhaust stock before creating order
        self.variant.stock = 1
        self.variant.save(update_fields=["stock"])
        with self.assertRaises(ValueError):
            OrderService.create_from_cart(
                cart=cart,
                created_by=self.customer,
                shipping_data={"city_id": 1, "region_id": 1},
            )
