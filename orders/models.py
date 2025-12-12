from decimal import Decimal
from django.db import models
from django.conf import settings
from accounts.models import ShippingAddress
from catalog.models import ProductVariant, Bundle
from django.core.validators import RegexValidator

iraq_phone_validator = RegexValidator(
    regex=r"^(?:\+964|00964|0)?7(7|8|9|5)\d{8}$",
    message="أدخل رقم هاتف عراقي صحيح (مثال: 07801234567 أو +9647801234567).",
)
try:
    from django.db.models import JSONField
except ImportError:
    from django.contrib.postgres.fields import JSONField


class Order(models.Model):
    """
    Order supports:
      - variants + bundles (mixed)
      - delivery vs pickup
      - different order types (normal, wholesale, replacement, exchange, cancellation)
      - handling of issue-related orders with restocking and free shipping flags
    """

    # a) delivery / pickup
    DELIVERY_METHOD_CHOICES = [
        ("delivery", "Delivery"),
        ("pickup", "Pick-up"),
    ]

    # c) order types
    ORDER_TYPE_CHOICES = [
        ("normal", "Normal"),
        ("wholesale", "Wholesale"),
        ("replacement", "Replacement"),
        ("exchange", "Exchange"),
        ("cancellation", "Cancellation"),
    ]

    # simple state machine for demo; you can expand it
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    code = models.CharField(max_length=50, unique=True)  # e.g. "ORD-2025-0001"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_orders",
    )
    # Who actually created the order (could be admin acting on behalf of customer)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_orders",
    )

    order_type = models.CharField(
        max_length=20, choices=ORDER_TYPE_CHOICES, default="normal"
    )
    delivery_method = models.CharField(
        max_length=20, choices=DELIVERY_METHOD_CHOICES, default="delivery"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # link to original order for issue-related orders (replacement, exchange, cancellation)
    related_order = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issue_orders",
    )

    shipping_profile = models.ForeignKey(
        ShippingAddress,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    # Snapshot shipping info at time of order (does NOT auto-update when profile changes)
    full_name = models.CharField(max_length=255, blank=True)
    city_id = models.IntegerField(blank=True)
    city = models.CharField(max_length=50, blank=True)
    region_id = models.IntegerField(blank=True)
    region = models.CharField(max_length=50, blank=True)
    location = models.TextField(blank=True)
    client_mobile2 = models.CharField(
        max_length=15,
        unique=True,
        validators=[iraq_phone_validator],
        blank=True,
        null=True,
    )
    # monetary fields
    items_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # NEW: discount snapshot from engine
    discount_breakdown = JSONField(null=True, blank=True)
    # Optional: profit snapshot (for analytics / debugging)
    profit_before_discounts = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    profit_after_discounts = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    # shipping info (for delivery)
    # shipping_name = models.CharField(max_length=255, blank=True)
    # shipping_address = models.CharField(max_length=255, blank=True)
    # shipping_city = models.CharField(max_length=100, blank=True)
    # shipping_postal_code = models.CharField(max_length=20, blank=True)
    # shipping_country = models.CharField(max_length=100, blank=True)
    # shipping_info = models.ForeignKey(
    #     ShippingAddress, on_delete=models.SET_NULL, null=True, related_name="order"
    # )

    # flags for issue-related logic
    is_free_shipping = models.BooleanField(
        default=False
    )  # for replacement / exchange if you decide
    restock_processed = models.BooleanField(default=False)  # to avoid double-restocking

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Order {self.code} ({self.order_type})"

    # b) derived properties
    @property
    def is_issue_order(self) -> bool:
        return self.order_type in ("replacement", "exchange", "cancellation")

    @property
    def is_admin_only_type(self) -> bool:
        # c) wholesale, replacement, exchange, cancellation must be created by admin
        return self.order_type in (
            "wholesale",
            "replacement",
            "exchange",
            "cancellation",
        )

    def recalculate_totals(self):
        total = sum(line.subtotal for line in self.lines.all())
        self.items_total = total
        # shipping_cost, discount_total etc. usually set by service/business logic
        self.grand_total = self.items_total + self.shipping_cost - self.discount_total
        self.save()

    # d) hooks for restocking logic
    def process_restocking(self):
        """
        For issue-related orders (replacement, exchange, cancellation),
        adjust inventory back (or partially) for variants.
        The exact logic belongs in your service layer – this method is a hook.
        """
        if not self.is_issue_order or self.restock_processed:
            return

        for line in self.lines.all():
            if line.line_type == "variant" and line.variant:
                # simplistic example: full restock of returned items
                line.variant.stock = models.F("stock") + line.quantity
                line.variant.save(update_fields=["stock"])
            elif line.line_type == "bundle" and line.bundle:
                # restock each variant inside the bundle according to its quantity
                for item in line.bundle.items.select_related("variant"):
                    item.variant.stock = models.F("stock") + (
                        item.quantity * line.quantity
                    )
                    item.variant.save(update_fields=["stock"])

        self.restock_processed = True
        self.save()


class OrderLine(models.Model):
    """
    One line in an order.
    Supports:
      - variant-based product
      - bundle
    Mixed orders are allowed (normal + bundle lines in same order).
    """

    LINE_TYPE_CHOICES = [
        ("variant", "Variant"),
        ("bundle", "Bundle"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    line_type = models.CharField(max_length=10, choices=LINE_TYPE_CHOICES)

    variant = models.ForeignKey(
        ProductVariant,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="order_lines",
    )
    bundle = models.ForeignKey(
        Bundle,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="order_lines",
    )

    quantity = models.PositiveIntegerField(default=1)

    # snapshot fields at order time
    product_name = models.CharField(max_length=255, blank=True)
    bundle_name = models.CharField(max_length=255, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        if self.line_type == "variant" and self.variant:
            return f"{self.quantity} x {self.product_name or self.variant} in order {self.order.code}"
        if self.line_type == "bundle" and self.bundle:
            return f"{self.quantity} x {self.bundle_name or self.bundle.name} in order {self.order.code}"
        return f"OrderLine #{self.pk}"

    def save(self, *args, **kwargs):
        # auto snapshot name and subtotal if not set
        if self.line_type == "variant" and self.variant and not self.product_name:
            self.product_name = str(self.variant)
        if self.line_type == "bundle" and self.bundle and not self.bundle_name:
            self.bundle_name = self.bundle.name

        if not self.subtotal:
            self.subtotal = self.unit_price * self.quantity

        super().save(*args, **kwargs)
