from decimal import Decimal
from django.db import models
from django.conf import settings

from catalog.models import ProductVariant, Bundle


class Cart(models.Model):
    """
    Cart is only for registered users.
    One active cart per user in most systems (enforced at service layer).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="carts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional: mark if this cart has been converted to an order
    is_converted = models.BooleanField(default=False)

    def __str__(self):
        return f"Cart #{self.pk} for {self.user.phone}"

    def items_total(self) -> Decimal:
        return sum(item.subtotal for item in self.items.all())

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    """
    Single line inside the cart.
    Can be either:
      - a normal product (via ProductVariant)
      - a bundle (via Bundle)
    Mixed carts are allowed.
    """

    LINE_TYPE_CHOICES = [
        ("variant", "Variant"),
        ("bundle", "Bundle"),
    ]

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    line_type = models.CharField(max_length=10, choices=LINE_TYPE_CHOICES)

    variant = models.ForeignKey(
        ProductVariant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    bundle = models.ForeignKey(
        Bundle,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    quantity = models.PositiveIntegerField(default=1)

    # snapshot of price at the time it was added (so later price changes don’t affect existing carts)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        # Optional: avoid duplicate lines (same item + same type per cart)
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "line_type", "variant", "bundle"],
                name="uniq_cart_item_per_type",
            )
        ]

    def __str__(self):
        if self.line_type == "variant" and self.variant:
            return f"{self.quantity} x {self.variant} in cart {self.cart_id}"
        if self.line_type == "bundle" and self.bundle:
            return f"{self.quantity} x Bundle {self.bundle.name} in cart {self.cart_id}"
        return f"CartItem #{self.pk}"

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity

    def clean(self):
        """
        Ensure the line_type matches which FK is set.
        Enforce this in service layer or override save() as you prefer.
        """
        if self.line_type == "variant" and not self.variant:
            raise ValueError("Variant cart item must have variant set.")
        if self.line_type == "bundle" and not self.bundle:
            raise ValueError("Bundle cart item must have bundle set.")
        if self.line_type == "variant" and self.bundle:
            raise ValueError("Variant line cannot have bundle.")
        if self.line_type == "bundle" and self.variant:
            raise ValueError("Bundle line cannot have variant.")
