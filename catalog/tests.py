from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import (
    Product,
    ProductVariant,
    VariantOption,
    VariantOptionValue,
    TieredPrice,
)
from catalog.services import resolve_price
from catalog.serializers import ProductVariantSerializer, TieredPriceSerializer


class CatalogTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_product_slug_and_default_variant_created(self):
        product = Product.objects.create(name="Arabic منتج")
        self.assertTrue(product.slug)
        self.assertTrue(product.variants.exists())

    def test_resolve_price_prefers_matching_tier(self):
        product = Product.objects.create(name="Tiers")
        variant = ProductVariant.objects.create(
            product=product,
            name="V1",
            sale_price=Decimal("10.00"),
            cost_price=Decimal("5.00"),
            wholesale_price=Decimal("8.00"),
            stock=5,
            sku="SKU-EXTRA-1",
            barcode="BAR-EXTRA-1",
            pricing_mode="tiered",
        )
        low = TieredPrice.objects.create(
            variant=variant,
            basis="quantity",
            unit="pcs",
            min_value=0,
            max_value=10,
            sale_price=Decimal("9.00"),
            cost_price=0,
            wholesale_price=0,
        )
        high = TieredPrice.objects.create(
            variant=variant,
            basis="quantity",
            unit="pcs",
            min_value=10,
            max_value=None,
            sale_price=Decimal("7.00"),
            cost_price=0,
            wholesale_price=0,
        )

        price, basis, tier_id = resolve_price(variant, quantity=Decimal("5"))
        self.assertEqual(price, low.sale_price)
        self.assertEqual(basis, "quantity")
        self.assertEqual(tier_id, low.id)

        price, basis, tier_id = resolve_price(variant, quantity=Decimal("15"))
        self.assertEqual(price, high.sale_price)
        self.assertEqual(basis, "quantity")
        self.assertEqual(tier_id, high.id)

    def test_variant_serializer_sets_option_values(self):
        product = Product.objects.create(name="Options")
        opt = VariantOption.objects.create(name="Color")
        red = VariantOptionValue.objects.create(option=opt, value="Red")
        blue = VariantOptionValue.objects.create(option=opt, value="Blue")

        data = {
            "name": "With Options",
            "sale_price": "5.00",
            "cost_price": "3.00",
            "wholesale_price": "4.00",
            "stock": 1,
            "sku": "SKU-OPT",
            "barcode": "BAR-OPT",
            "pricing_mode": "flat",
            "share_inventory_across_tiers": True,
            "option_value_ids": [red.id, blue.id],
        }
        serializer = ProductVariantSerializer(data=data, context={"product": product})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        variant = serializer.save(product=product)
        self.assertEqual(variant.options.count(), 2)

    def test_tier_serializer_prevents_overlaps_and_invalid_range(self):
        product = Product.objects.create(name="Tier Validation")
        variant = ProductVariant.objects.create(
            product=product,
            name="V1",
            sale_price=Decimal("10.00"),
            cost_price=Decimal("5.00"),
            wholesale_price=Decimal("8.00"),
            stock=5,
            sku="SKU-TIER",
            barcode="BAR-TIER",
            pricing_mode="tiered",
        )
        TieredPrice.objects.create(
            variant=variant,
            basis="quantity",
            unit="pcs",
            min_value=0,
            max_value=10,
            sale_price=Decimal("9.00"),
            cost_price=0,
            wholesale_price=0,
        )

        bad_overlap = TieredPriceSerializer(
            data={
                "variant_id": variant.id,
                "basis": "quantity",
                "unit": "pcs",
                "min_value": 5,
                "max_value": 15,
                "sale_price": "8.00",
                "cost_price": "0",
                "wholesale_price": "0",
            }
        )
        self.assertFalse(bad_overlap.is_valid())

        bad_range = TieredPriceSerializer(
            data={
                "variant_id": variant.id,
                "basis": "quantity",
                "unit": "pcs",
                "min_value": 5,
                "max_value": 5,
                "sale_price": "8.00",
                "cost_price": "0",
                "wholesale_price": "0",
            }
        )
        self.assertFalse(bad_range.is_valid())

    def test_product_list_filters_in_stock(self):
        p1 = Product.objects.create(name="Out")
        ProductVariant.objects.create(
            product=p1,
            name="v1",
            sale_price=Decimal("1.00"),
            cost_price=Decimal("0.50"),
            wholesale_price=Decimal("0.80"),
            stock=0,
            sku="SKU-OUT",
            barcode="BAR-OUT",
        )
        p2 = Product.objects.create(name="In")
        ProductVariant.objects.create(
            product=p2,
            name="v2",
            sale_price=Decimal("2.00"),
            cost_price=Decimal("1.00"),
            wholesale_price=Decimal("1.50"),
            stock=5,
            sku="SKU-IN",
            barcode="BAR-IN",
        )

        res = self.client.get("/api/catalog/products/", {"in_stock": "true"})
        self.assertEqual(res.status_code, 200)
        names = [item["name"] for item in res.data]
        self.assertIn("In", names)
        self.assertNotIn("Out", names)
