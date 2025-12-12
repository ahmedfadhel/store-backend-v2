from decimal import Decimal
from django.db import models
from django.utils import timezone
from catalog.models import ProductVariant
from carts.models import Cart


class Discount(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ("product_override", "Product-level price override"),
        ("cart_subtotal", "Cart subtotal discount"),
        ("coupon", "Coupon"),
        ("flash_sale", "Flash sale"),
        ("abandoned_cart", "Abandoned cart"),
    ]

    VALUE_TYPE_CHOICES = [
        ("percent", "Percent"),
        ("fixed", "Fixed amount"),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Required for coupon-type discounts",
    )
    discount_type = models.CharField(max_length=30, choices=DISCOUNT_TYPE_CHOICES)
    value_type = models.CharField(
        max_length=10, choices=VALUE_TYPE_CHOICES, default="percent"
    )
    value = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="If percent, 10 = 10%"
    )

    # Admin controls / scheduling
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    # Priority + stacking
    priority = models.IntegerField(default=100, help_text="Lower = applied earlier")
    stackable = models.BooleanField(
        default=True, help_text="Can it be combined with others?"
    )
    exclusive = models.BooleanField(
        default=False, help_text="If applied, stop applying lower priority discounts"
    )

    # Optional conditions
    min_cart_subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    # For abandoned cart discounts (e.g. cart idle >= 60 minutes)
    min_abandoned_minutes = models.IntegerField(null=True, blank=True)

    # Limit how much profit can be eaten by this single discount (0–1.0)
    max_profit_share = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("0.75"),
        help_text="Max % of profit this discount can consume. 0.75 = 75%.",
    )

    # Target variants (for product_override / flash_sale / coupon limited to specific variants)
    target_variants = models.ManyToManyField(
        ProductVariant,
        blank=True,
        related_name="discounts",
        help_text="Empty = applies to all variants (for non-product specific types)",
    )

    # For product-level overrides we can store override price
    # override_price = models.DecimalField(
    #     max_digits=10,
    #     decimal_places=2,
    #     null=True,
    #     blank=True,
    #     help_text="Used only for product_override / flash_sale if you want direct override"
    # )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.discount_type})"

    def is_currently_active(self) -> bool:
        if not self.is_active:
            return False
        now = timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True

    @property
    def requires_coupon_code(self) -> bool:
        return self.discount_type == "coupon"
