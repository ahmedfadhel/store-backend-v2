from decimal import Decimal
from rest_framework import serializers
from .models import (
    Product,
    ProductVariant,
    VariantOptionValue,
    Bundle,
    TieredPrice,
    BundleItem,
)


class VariantOptionValueSerializer(serializers.ModelSerializer):
    option_name = serializers.CharField(source="option.name")

    class Meta:
        model = VariantOptionValue
        fields = ["id", "option_name", "value", "color_code"]


class TieredPriceSerializer(serializers.ModelSerializer):
    variant_id = serializers.PrimaryKeyRelatedField(
        source="variant", queryset=ProductVariant.objects.all(), write_only=True
    )

    class Meta:
        model = TieredPrice
        fields = [
            "id",
            "variant_id",
            "basis",
            "unit",
            "min_value",
            "max_value",
            "step",
            "sale_price",
            "cost_price",
            "wholesale_price",
            "sku_suffix",
            "barcode",
        ]

    def validate(self, attrs):
        min_value = attrs.get("min_value", self.instance.min_value if self.instance else None)
        max_value = attrs.get("max_value", self.instance.max_value if self.instance else None)
        if max_value is not None and min_value is not None and max_value <= min_value:
            raise serializers.ValidationError("max_value must be greater than min_value.")

        variant = attrs.get("variant", getattr(self.instance, "variant", None))
        basis = attrs.get("basis", getattr(self.instance, "basis", None))
        unit = attrs.get("unit", getattr(self.instance, "unit", None))

        if variant and basis and unit:
            qs = TieredPrice.objects.filter(variant=variant, basis=basis, unit=unit)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            for tp in qs:
                existing_min = tp.min_value
                existing_max = tp.max_value if tp.max_value is not None else Decimal("Infinity")
                new_min = min_value
                new_max = max_value if max_value is not None else Decimal("Infinity")
                if new_min < existing_max and new_max > existing_min:
                    raise serializers.ValidationError(
                        "Tier range overlaps with an existing tier for this variant/basis/unit."
                    )

        return attrs


class ProductVariantSerializer(serializers.ModelSerializer):
    options = VariantOptionValueSerializer(many=True, read_only=True)
    option_value_ids = serializers.PrimaryKeyRelatedField(
        source="options",
        queryset=VariantOptionValue.objects.all(),
        many=True,
        write_only=True,
        required=False,
    )
    color_code = serializers.ReadOnlyField()
    pricing_mode = serializers.ChoiceField(choices=ProductVariant.PRICING_MODE)
    tiers = TieredPriceSerializer(many=True, read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "name",
            "sale_price",
            "cost_price",
            "wholesale_price",
            "stock",
            "sku",
            "barcode",
            "image",
            "options",
            "option_value_ids",
            "color_code",
            "pricing_mode",
            "share_inventory_across_tiers",
            "tiers",
        ]

    def create(self, validated_data):
        option_values = validated_data.pop("options", [])
        variant = super().create(validated_data)
        if option_values:
            variant.options.set(option_values)
        return variant

    def update(self, instance, validated_data):
        option_values = validated_data.pop("options", None)
        variant = super().update(instance, validated_data)
        if option_values is not None:
            variant.options.set(option_values)
        return variant


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True)
    lowest_price = serializers.SerializerMethodField()
    price_label = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "main_image",
            "lowest_price",
            "price_label",
            "variants",
        ]

    def get_lowest_price(self, obj):
        return obj.lowest_price()

    def get_price_label(self, obj):
        return (
            "Starts from {:.2f}".format(obj.lowest_price())
            if obj.variants.count() > 1
            or any(
                v.pricing_mode == "tiered" and v.tiers.exists()
                for v in obj.variants.all()
            )
            else "{:.2f}".format(obj.lowest_price())
        )


class BundleVariantMiniSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name")

    class Meta:
        model = ProductVariant
        fields = ["id", "product_name", "name", "sale_price", "sku", "image"]


class BundleItemSerializer(serializers.ModelSerializer):
    variant = BundleVariantMiniSerializer(read_only=True)
    variant_id = serializers.PrimaryKeyRelatedField(
        source="variant", queryset=ProductVariant.objects.all(), write_only=True
    )

    class Meta:
        model = BundleItem
        fields = ["id", "variant", "variant_id", "quantity"]


class BundleSerializer(serializers.ModelSerializer):
    items = BundleItemSerializer(many=True, read_only=True)
    total_regular_price = serializers.SerializerMethodField()

    class Meta:
        model = Bundle
        fields = [
            "id",
            "name",
            "description",
            "bundle_price",
            "image",
            "total_regular_price",
            "items",
        ]

    def get_total_regular_price(self, obj):
        return obj.total_regular_price()
