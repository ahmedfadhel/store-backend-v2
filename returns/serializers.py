# returns/serializers.py

from rest_framework import serializers
from returns.models import ReturnRequest, ReturnRequestLine
from orders.models import Order, OrderLine


# ---- Mini serializer for showing original line info ----
class OrderLineMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLine
        fields = [
            "id",
            "line_type",
            "product_name",
            "bundle_name",
            "quantity",
            "unit_price",
            "subtotal",
        ]


# ---- Read-only line serializer ----
class ReturnRequestLineSerializer(serializers.ModelSerializer):
    order_line = OrderLineMiniSerializer(read_only=True)

    class Meta:
        model = ReturnRequestLine
        fields = [
            "id",
            "order_line",
            "requested_quantity",
            "reason_code",
            "reason_text",
        ]


# ---- Nested line serializer for creation ----
class ReturnRequestLineCreateSerializer(serializers.Serializer):
    order_line_id = serializers.IntegerField()
    requested_quantity = serializers.IntegerField(min_value=1)
    reason_code = serializers.ChoiceField(choices=ReturnRequestLine.REASON_CHOICES)
    reason_text = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        order_line_id = attrs["order_line_id"]
        requested_quantity = attrs["requested_quantity"]

        try:
            order_line = OrderLine.objects.get(pk=order_line_id)
        except OrderLine.DoesNotExist:
            raise serializers.ValidationError("Order line not found.")

        # TODO (optional): check not exceeding remaining quantity
        # already_requested = sum(l.requested_quantity for l in order_line.return_lines.all())
        # if requested_quantity + already_requested > order_line.quantity:
        #     raise serializers.ValidationError("Requested quantity exceeds purchased quantity.")

        attrs["order_line"] = order_line
        return attrs


# ---- Read serializer for ReturnRequest ----
class ReturnRequestSerializer(serializers.ModelSerializer):
    lines = ReturnRequestLineSerializer(many=True, read_only=True)
    original_order_code = serializers.CharField(
        source="original_order.code", read_only=True
    )

    class Meta:
        model = ReturnRequest
        fields = [
            "id",
            "customer",
            "original_order",
            "original_order_code",
            "status",
            "resolution",
            "reason_general",
            "created_at",
            "updated_at",
            "return_issue_order",
            "replacement_order",
            "lines",
        ]
        read_only_fields = ["customer", "created_at", "updated_at"]


# ---- Create serializer (customer creates request) ----
class ReturnRequestCreateSerializer(serializers.Serializer):
    original_order_id = serializers.IntegerField()
    resolution = serializers.ChoiceField(
        choices=ReturnRequest.RESOLUTION_CHOICES,
        default="refund",
    )
    reason_general = serializers.CharField(required=False, allow_blank=True)
    lines = ReturnRequestLineCreateSerializer(many=True)

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user

        # validate original order
        try:
            order = Order.objects.get(pk=attrs["original_order_id"])
        except Order.DoesNotExist:
            raise serializers.ValidationError("Original order not found.")

        # only allow returns for your own orders (unless admin)
        if not (
            getattr(user, "is_admin", False) or getattr(user, "is_employee", False)
        ):
            if order.customer != user:
                raise serializers.ValidationError(
                    "You can only return your own orders."
                )

        # optional: only allow returns for delivered/completed orders
        if order.status not in ("completed", "shipped"):
            raise serializers.ValidationError(
                "You can only return completed or shipped orders."
            )

        attrs["original_order"] = order

        # ensure at least one line
        if not attrs["lines"]:
            raise serializers.ValidationError("At least one line must be provided.")

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        order = validated_data["original_order"]

        # choose customer: original order's customer
        customer = order.customer

        rr = ReturnRequest.objects.create(
            customer=customer,
            original_order=order,
            resolution=validated_data["resolution"],
            reason_general=validated_data.get("reason_general", ""),
            status="pending",
        )

        for line_data in validated_data["lines"]:
            ReturnRequestLine.objects.create(
                return_request=rr,
                order_line=line_data["order_line"],
                requested_quantity=line_data["requested_quantity"],
                reason_code=line_data["reason_code"],
                reason_text=line_data.get("reason_text", ""),
            )

        return rr
