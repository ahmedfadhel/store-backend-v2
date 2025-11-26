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
    class Meta:
        model = TieredPrice
        fields = [
            "id",
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


class ProductVariantSerializer(serializers.ModelSerializer):
    options = VariantOptionValueSerializer(many=True)
    color_code = serializers.ReadOnlyField()
    pricing_mode = serializers.CharField(read_only=False)
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
            "color_code",
            "pricing_mode",
            "share_inventory_across_tiers",
            "tiers",
        ]


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
