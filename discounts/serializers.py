from rest_framework import serializers
from .models import Discount
from catalog.models import ProductVariant
from carts.models import Cart
from .engine import DiscountEngine


class DiscountSerializer(serializers.ModelSerializer):
    target_variants = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(), many=True, required=False
    )

    class Meta:
        model = Discount
        fields = [
            "id",
            "name",
            "code",
            "discount_type",
            "value_type",
            "value",
            "is_active",
            "starts_at",
            "ends_at",
            "priority",
            "stackable",
            "exclusive",
            "min_cart_subtotal",
            "min_abandoned_minutes",
            "max_profit_share",
            "target_variants",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class ApplyDiscountRequestSerializer(serializers.Serializer):
    cart_id = serializers.IntegerField()
    coupon_code = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        from django.shortcuts import get_object_or_404

        request = self.context["request"]
        user = request.user

        cart = get_object_or_404(Cart, pk=attrs["cart_id"])
        # ensure user owns the cart or is admin
        if cart.user != user and not (
            getattr(user, "is_admin", False) or getattr(user, "is_employee", False)
        ):
            raise serializers.ValidationError(
                "You cannot apply discounts to another user's cart."
            )

        attrs["cart"] = cart
        return attrs

    def create(self, validated_data):
        cart = validated_data["cart"]
        coupon = validated_data.get("coupon_code") or None
        result = DiscountEngine.apply_discounts(cart, coupon)
        return result


class DiscountedCartSerializer(serializers.Serializer):
    original_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    discounted_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_discount = serializers.DecimalField(max_digits=10, decimal_places=2)
    profit_before = serializers.DecimalField(max_digits=10, decimal_places=2)
    profit_after = serializers.DecimalField(max_digits=10, decimal_places=2)
    applied_discounts = serializers.ListField()

    @classmethod
    def from_result(cls, result):
        return cls(
            {
                "original_total": result.original_total,
                "discounted_total": result.discounted_total,
                "total_discount": result.total_discount,
                "profit_before": result.profit_before,
                "profit_after": result.profit_after,
                "applied_discounts": result.applied_discounts,
            }
        )
