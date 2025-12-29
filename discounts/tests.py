from decimal import Decimal
from django.test import TestCase
from accounts.models import User
from carts.models import Cart, CartItem
from catalog.models import Product, ProductVariant, Bundle, BundleItem
from discounts.models import Discount
from discounts.engine import DiscountEngine


class DiscountEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="07700000004", password="pass")
        self.user.is_active = True
        self.user.save()
        self.product = Product.objects.create(name="Disc Product")
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Disc Variant",
            sale_price=Decimal("100.00"),
            cost_price=Decimal("50.00"),
            wholesale_price=Decimal("80.00"),
            stock=10,
            sku="SKU-DISC",
            barcode="BAR-DISC",
        )

    def _build_cart_with_variant(self, qty=1, price=None):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=cart,
            line_type="variant",
            variant=self.variant,
            quantity=qty,
            unit_price=price or self.variant.sale_price,
        )
        return cart

    def test_profit_cap_limits_discount(self):
        cart = self._build_cart_with_variant()
        Discount.objects.create(
            name="Big Percent",
            discount_type="cart_subtotal",
            value_type="percent",
            value=Decimal("50.00"),
            max_profit_share=Decimal("1.00"),
        )
        result = DiscountEngine.apply_discounts(cart)
        # Profit before = (100 - 50) = 50, cap at 25% => 12.5
        self.assertEqual(result.total_discount, Decimal("12.5"))
        self.assertEqual(result.discounted_total, Decimal("87.5"))

    def test_bundle_costs_in_profit_calculation(self):
        bundle = Bundle.objects.create(
            name="Bundle", description="", slug="bundle", bundle_price=Decimal("20.00")
        )
        BundleItem.objects.create(bundle=bundle, variant=self.variant, quantity=1)
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=cart,
            line_type="bundle",
            bundle=bundle,
            quantity=1,
            unit_price=Decimal("20.00"),
        )
        result = DiscountEngine.apply_discounts(cart)
        self.assertEqual(result.original_total, Decimal("20.00"))
        self.assertEqual(result.profit_before, Decimal("0.00"))
