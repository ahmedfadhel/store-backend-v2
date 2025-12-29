from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User, ShippingAddress
from catalog.models import (
    Product,
    ProductVariant,
    VariantOption,
    VariantOptionValue,
    ProductImage,
    TieredPrice,
    Bundle,
    BundleItem,
)
from discounts.models import Discount
from carts.models import Cart


class Command(BaseCommand):
    help = "Seed demo data for Postman testing (users, catalog, bundle, discounts, cart)."

    @transaction.atomic
    def handle(self, *args, **options):
        # --- Users ---
        admin, _ = User.objects.get_or_create(
            phone="07700000001",
            defaults={"role": "admin", "is_staff": True, "is_superuser": True, "is_active": True},
        )
        admin.set_password("AdminPass123")
        admin.is_active = True
        admin.save()

        employee, _ = User.objects.get_or_create(
            phone="07700000002",
            defaults={"role": "employee", "is_staff": True, "is_active": True},
        )
        employee.set_password("EmployeePass123")
        employee.is_active = True
        employee.save()

        customer, _ = User.objects.get_or_create(
            phone="07700000003",
            defaults={"role": "customer", "is_active": True},
        )
        customer.set_password("CustomerPass123")
        customer.is_active = True
        customer.save()

        ShippingAddress.objects.update_or_create(
            user=customer,
            defaults={
                "full_name": "Demo Customer",
                "city_id": 1,
                "city": "Baghdad",
                "region_id": 10,
                "region": "Karrada",
                "location": "Demo street 123",
                "client_mobile2": None,
            },
        )

        # --- Variant options ---
        color_opt, _ = VariantOption.objects.get_or_create(name="Color")
        red, _ = VariantOptionValue.objects.get_or_create(
            option=color_opt, value="Red", color_code="#ff0000"
        )
        blue, _ = VariantOptionValue.objects.get_or_create(
            option=color_opt, value="Blue", color_code="#0000ff"
        )

        size_opt, _ = VariantOption.objects.get_or_create(name="Size")
        small, _ = VariantOptionValue.objects.get_or_create(option=size_opt, value="Small")
        large, _ = VariantOptionValue.objects.get_or_create(option=size_opt, value="Large")

        # --- Products & variants ---
        # Multi-variant example
        candle, _ = Product.objects.get_or_create(
            name="Scented Candle",
            defaults={"description": "Vanilla scented candle", "is_active": True},
        )
        candle_variant_red, _ = ProductVariant.objects.get_or_create(
            product=candle,
            name="Red Candle",
            defaults={
                "sale_price": Decimal("15.00"),
                "cost_price": Decimal("7.00"),
                "wholesale_price": Decimal("12.00"),
                "stock": 200,
                "sku": "CND-RED",
                "barcode": "CND-RED-001",
            },
        )
        candle_variant_red.options.set([red, small])

        candle_variant_blue, _ = ProductVariant.objects.get_or_create(
            product=candle,
            name="Blue Candle",
            defaults={
                "sale_price": Decimal("17.00"),
                "cost_price": Decimal("8.00"),
                "wholesale_price": Decimal("13.00"),
                "stock": 150,
                "sku": "CND-BLU",
                "barcode": "CND-BLU-001",
            },
        )
        candle_variant_blue.options.set([blue, large])

        # Gallery images on the candle product
        ProductImage.objects.get_or_create(
            product=candle,
            image="products/gallery/candle-hero.jpg",
            defaults={"alt_text": "Scented candle hero shot"},
        )
        ProductImage.objects.get_or_create(
            product=candle,
            image="products/gallery/candle-closeup.jpg",
            defaults={"alt_text": "Candle wick close-up"},
        )

        # Single-variant example (flat pricing)
        wax, _ = Product.objects.get_or_create(
            name="Wax Pack",
            defaults={"description": "1kg wax pack", "is_active": True},
        )
        wax_variant, _ = ProductVariant.objects.get_or_create(
            product=wax,
            name="Wax 1kg",
            defaults={
                "sale_price": Decimal("10.00"),
                "cost_price": Decimal("4.00"),
                "wholesale_price": Decimal("8.00"),
                "stock": 300,
                "sku": "WAX-1KG",
                "barcode": "WAX-1KG-001",
            },
        )

        # Single-variant example with tiered pricing by quantity/weight
        coffee, _ = Product.objects.get_or_create(
            name="Premium Coffee Beans",
            defaults={
                "description": "Bulk single-origin coffee beans sold with tiered pricing.",
                "is_active": True,
            },
        )
        coffee_variant, _ = ProductVariant.objects.get_or_create(
            product=coffee,
            name="Roasted Beans",
            defaults={
                "pricing_mode": "tiered",
                "sale_price": Decimal("18.00"),
                "cost_price": Decimal("9.00"),
                "wholesale_price": Decimal("15.00"),
                "stock": 500,
                "sku": "COF-BEAN",
                "barcode": "COF-BEAN-001",
            },
        )
        if coffee_variant.pricing_mode != "tiered":
            coffee_variant.pricing_mode = "tiered"
            coffee_variant.save(update_fields=["pricing_mode"])

        # Quantity-based tiers
        TieredPrice.objects.update_or_create(
            variant=coffee_variant,
            basis="quantity",
            unit="pcs",
            min_value=Decimal("1"),
            max_value=Decimal("5"),
            defaults={
                "sale_price": Decimal("18.00"),
                "cost_price": Decimal("9.00"),
                "wholesale_price": Decimal("15.00"),
                "step": Decimal("1"),
                "sku_suffix": "-qty1-4",
                "barcode": "COF-QTY-001",
            },
        )
        TieredPrice.objects.update_or_create(
            variant=coffee_variant,
            basis="quantity",
            unit="pcs",
            min_value=Decimal("5"),
            max_value=Decimal("10"),
            defaults={
                "sale_price": Decimal("16.00"),
                "cost_price": Decimal("8.00"),
                "wholesale_price": Decimal("14.00"),
                "step": Decimal("1"),
                "sku_suffix": "-qty5-9",
                "barcode": "COF-QTY-002",
            },
        )
        TieredPrice.objects.update_or_create(
            variant=coffee_variant,
            basis="quantity",
            unit="pcs",
            min_value=Decimal("10"),
            max_value=None,
            defaults={
                "sale_price": Decimal("14.00"),
                "cost_price": Decimal("7.00"),
                "wholesale_price": Decimal("12.00"),
                "step": Decimal("1"),
                "sku_suffix": "-qty10plus",
                "barcode": "COF-QTY-003",
            },
        )

        # Weight-based tiers
        TieredPrice.objects.update_or_create(
            variant=coffee_variant,
            basis="weight",
            unit="kg",
            min_value=Decimal("0.25"),
            max_value=Decimal("1.00"),
            defaults={
                "sale_price": Decimal("5.50"),
                "cost_price": Decimal("3.00"),
                "wholesale_price": Decimal("4.50"),
                "step": Decimal("0.25"),
                "sku_suffix": "-250g-999g",
                "barcode": "COF-WGT-001",
            },
        )
        TieredPrice.objects.update_or_create(
            variant=coffee_variant,
            basis="weight",
            unit="kg",
            min_value=Decimal("1.00"),
            max_value=Decimal("5.00"),
            defaults={
                "sale_price": Decimal("20.00"),
                "cost_price": Decimal("10.00"),
                "wholesale_price": Decimal("16.00"),
                "step": Decimal("0.50"),
                "sku_suffix": "-1kg-4kg",
                "barcode": "COF-WGT-002",
            },
        )
        TieredPrice.objects.update_or_create(
            variant=coffee_variant,
            basis="weight",
            unit="kg",
            min_value=Decimal("5.00"),
            max_value=None,
            defaults={
                "sale_price": Decimal("90.00"),
                "cost_price": Decimal("45.00"),
                "wholesale_price": Decimal("75.00"),
                "step": Decimal("1.00"),
                "sku_suffix": "-5kgplus",
                "barcode": "COF-WGT-003",
            },
        )

        # --- Bundle ---
        bundle, _ = Bundle.objects.get_or_create(
            name="Candle Gift Bundle",
            defaults={"description": "Red candle + wax pack", "bundle_price": Decimal("22.00")},
        )
        BundleItem.objects.get_or_create(bundle=bundle, variant=candle_variant_red, defaults={"quantity": 1})
        BundleItem.objects.get_or_create(bundle=bundle, variant=wax_variant, defaults={"quantity": 1})

        # --- Discounts ---
        # Product-level discount on Blue Candle (still allowed with bundles in cart)
        Discount.objects.get_or_create(
            name="Blue Candle 20% Off",
            discount_type="flash_sale",
            value_type="percent",
            value=Decimal("20"),
            priority=10,
            defaults={"is_active": True},
        )[0].target_variants.add(candle_variant_blue)

        # Coupon (ignored when bundle exists per discount engine option 1)
        Discount.objects.get_or_create(
            name="WELCOME10",
            code="WELCOME10",
            discount_type="coupon",
            value_type="percent",
            value=Decimal("10"),
            priority=20,
            defaults={"is_active": True},
        )

        # Cart subtotal discount (also ignored with bundles present)
        Discount.objects.get_or_create(
            name="Cart 5 Fixed",
            discount_type="cart_subtotal",
            value_type="fixed",
            value=Decimal("5.00"),
            priority=30,
            defaults={"is_active": True},
        )

        # --- Cart with lines for the customer ---
        cart = customer.carts.first() or Cart.objects.create(user=customer)
        cart.items.all().delete()  # reset for repeatable runs
        cart.items.create(
            line_type="variant",
            variant=candle_variant_blue,
            quantity=2,
            unit_price=candle_variant_blue.sale_price,
        )
        cart.items.create(
            line_type="bundle",
            bundle=bundle,
            quantity=1,
            unit_price=bundle.bundle_price,
        )
        cart.save()

        self.stdout.write(self.style.SUCCESS("Seed data created."))
        self.stdout.write("Admin login: 07700000001 / AdminPass123")
        self.stdout.write("Employee login: 07700000002 / EmployeePass123")
        self.stdout.write("Customer login: 07700000003 / CustomerPass123")
        self.stdout.write("Coupon: WELCOME10 (ignored if bundle present)")
