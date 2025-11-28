from django.db import models
from django.db.models import Min
from django.utils.text import slugify
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from .utils import unique_slugify


# ------------------------------
#  PRODUCT
# ------------------------------
class Product(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, allow_unicode=True)
    description = models.TextField(blank=True)
    main_image = models.ImageField(upload_to="products/main/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        if not (self.pk):
            self.slug = unique_slugify(self, self.name)

        else:
            old = type(self).objects.get(pk=self.pk)

            if old.name != self.name:

                self.slug = unique_slugify(self, self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    # ---------- Price summary for frontend ----------
    def lowest_price(self):
        # look across all variants; each variant returns its own effective lowest price
        prices = [v.effective_lowest_price() for v in self.variants.all()]
        return (
            min(p for p in prices if p is not None) if prices else Decimal("0")
        ) or Decimal("0")

    def price_label(self):
        """Returns 'starts from' if multiple variants exist."""
        if self.variants.count() > 1:
            return f"Starts from {self.lowest_price():.2f}"
        return f"{self.lowest_price():.2f}"

    # ---------- Default variant auto-creation ----------
    def ensure_default_variant(self):
        if not self.variants.exists():
            ProductVariant.objects.create(
                product=self,
                name=f"{self.name} (Default)",
                sale_price=0,
                cost_price=0,
                wholesale_price=0,
                stock=0,
                sku=f"SKU-{self.pk}",
                barcode=f"BAR-{self.pk}",
            )


@receiver(post_save, sender=Product)
def create_default_variant(sender, instance, created, **kwargs):
    if created:
        instance.ensure_default_variant()


# ------------------------------
#  VARIANT OPTIONS
# ------------------------------
class VariantOption(models.Model):
    name = models.CharField(max_length=50)  # e.g. Color, Weight, Shape

    def __str__(self):
        return self.name


class VariantOptionValue(models.Model):
    option = models.ForeignKey(
        VariantOption, on_delete=models.CASCADE, related_name="values"
    )
    value = models.CharField(max_length=50)  # e.g. Red, 500g
    color_code = models.CharField(
        max_length=10, blank=True, null=True
    )  # optional color hex

    def __str__(self):
        return f"{self.option.name}: {self.value}"


# ------------------------------
#  PRODUCT VARIANT
# ------------------------------
class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to="products/variants/", null=True, blank=True)
    PRICING_MODE = [("flat", "Flat"), ("tiered", "Tiered")]
    pricing_mode = models.CharField(max_length=10, choices=PRICING_MODE, default="flat")
    # Inventory info
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=100, unique=True)
    barcode = models.CharField(max_length=100, unique=True)
    share_inventory_across_tiers = models.BooleanField(default=True)

    # Relations to variant attributes
    options = models.ManyToManyField(
        VariantOptionValue, blank=True, related_name="variants"
    )

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    @property
    def color_code(self):
        """Return color hex if color option exists."""
        color_opt = self.options.filter(option__name__iexact="color").first()
        return color_opt.color_code if color_opt else None

    def effective_lowest_price(self):
        """Min price among tiers if tiered, else the variant's sale_price."""
        if self.pricing_mode == "tiered" and self.tiers.exists():
            return self.tiers.aggregate(m=models.Min("sale_price"))["m"] or Decimal("0")
        return self.sale_price


# New: per-variant tiered prices (by quantity or weight)
class TieredPrice(models.Model):
    BASIS = [("quantity", "Quantity"), ("weight", "Weight")]
    UNIT = [
        ("pcs", "Pieces"),
        ("g", "Grams"),
        ("kg", "Kilograms"),
        ("ml", "Milliliters"),
        ("l", "Liters"),
    ]

    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="tiers"
    )
    basis = models.CharField(max_length=10, choices=BASIS)  # quantity | weight
    unit = models.CharField(max_length=10, choices=UNIT)  # g, kg, pcs, etc.

    # Range for which this price applies (closed-open: [min, max) )
    min_value = models.DecimalField(
        max_digits=10, decimal_places=3, validators=[MinValueValidator(0)]
    )
    max_value = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )  # None = no upper limit
    step = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )  # optional UI guidance

    # Prices for this slice
    sale_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0
    )
    wholesale_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0
    )

    # Optional SKU/barcode per tier (kept optional since inventory is shared on the variant)
    sku_suffix = models.CharField(max_length=40, blank=True)  # e.g., "-500g" or "-x10"
    barcode = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "basis", "unit", "min_value", "max_value"],
                name="uniq_variant_tier_range",
            )
        ]
        ordering = ["basis", "unit", "min_value"]

    def __str__(self):
        up = f"{self.max_value}" if self.max_value is not None else "∞"
        return f"{self.variant} [{self.basis} {self.unit} {self.min_value}–{up}) → {self.sale_price}"

    def matches(
        self, qty: Decimal | None = None, weight: Decimal | None = None
    ) -> bool:
        v = qty if self.basis == "quantity" else weight
        if v is None:
            return False
        if self.max_value is None:
            return v >= self.min_value
        return self.min_value <= v < self.max_value


# ------------------------------
#  PRODUCT IMAGE GALLERY
# ------------------------------
class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="products/gallery/")
    alt_text = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Image for {self.product.name}"


# ------------------------------
#  PRODUCT BUNDLE
# ------------------------------
class Bundle(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, blank=True, allow_unicode=True)
    bundle_price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="products/bundles/", null=True, blank=True)
    variants = models.ManyToManyField(
        "ProductVariant", through="BundleItem", related_name="bundles"
    )

    def save(self, *args, **kwargs):
        if not self.slug or slugify(self.name, allow_unicode=True) not in self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)

    def total_regular_price(self):
        """
        Sum of (variant effective lowest price * quantity in this bundle).
        If you don't use tiered prices, effective_lowest_price() just returns sale_price.
        """
        total = Decimal("0")
        for item in self.items.select_related("variant", "variant__product"):
            price = item.variant.effective_lowest_price()
            total += price * item.quantity
        return total

    def __str__(self):
        return self.name


class BundleItem(models.Model):
    """
    A single line inside a bundle:
    e.g. 2x 'Candle Red 250g' + 1x 'Wax 1kg'
    """

    bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        "ProductVariant", on_delete=models.CASCADE, related_name="bundle_items"
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("bundle", "variant")

    def __str__(self):
        return f"{self.quantity} x {self.variant} in {self.bundle.name}"
