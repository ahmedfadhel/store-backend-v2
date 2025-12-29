from decimal import Decimal
from django.test import TestCase
from accounts.models import User
from catalog.models import Product, ProductVariant, Bundle, BundleItem
from carts.models import Cart, CartItem


class CartValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="07700000001", password="pass")
        self.user.is_active = True
        self.user.save()
        self.cart = Cart.objects.create(user=self.user)
        self.product = Product.objects.create(name="Test Product")
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Default",
            sale_price=Decimal("10.00"),
            cost_price=Decimal("5.00"),
            wholesale_price=Decimal("8.00"),
            stock=5,
            sku="SKU-CART",
            barcode="BAR-CART",
        )

    def test_variant_stock_validation(self):
        with self.assertRaises(ValueError):
            CartItem.objects.create(
                cart=self.cart,
                line_type="variant",
                variant=self.variant,
                quantity=10,
                unit_price=Decimal("10.00"),
            )

    def test_bundle_stock_validation(self):
        bundle = Bundle.objects.create(
            name="Bundle", description="", slug="bundle", bundle_price=Decimal("20.00")
        )
        BundleItem.objects.create(bundle=bundle, variant=self.variant, quantity=3)
        with self.assertRaises(ValueError):
            CartItem.objects.create(
                cart=self.cart,
                line_type="bundle",
                bundle=bundle,
                quantity=2,
                unit_price=Decimal("20.00"),
            )
