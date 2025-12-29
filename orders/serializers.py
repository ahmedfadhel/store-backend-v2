from rest_framework import serializers
from orders.models import Order, OrderLine
from carts.models import Cart
from catalog.models import ProductVariant, Bundle
from .services import OrderService

from decimal import Decimal


class OrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLine
        fields = [
            "id",
            "line_type",
            "variant",
            "bundle",
            "product_name",
            "bundle_name",
            "quantity",
            "unit_price",
            "subtotal",
        ]
        read_only_fields = ["product_name", "bundle_name", "subtotal"]


class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "code",
            "customer",
            "created_by",
            "order_type",
            "delivery_method",
            "status",
            "related_order",
            "items_total",
            "shipping_cost",
            "discount_total",
            "grand_total",
            "full_name",
            "city_id",
            "city",
            "region_id",
            "region",
            "location",
            "client_mobile2",
            "is_free_shipping",
            "restock_processed",
            "notes",
            "created_at",
            "updated_at",
            "lines",
        ]
        read_only_fields = [
            "code",
            "created_by",
            "items_total",
            "grand_total",
            "restock_processed",
            "created_at",
            "updated_at",
        ]


# --------- Create Order From Cart (Customer + Admin) ---------


class CreateOrderFromCartSerializer(serializers.Serializer):
    """
    Used for both:
    - normal customer orders (order_type forcibly 'normal')
    - admin-created wholesale/issue orders (if allowed).
    """

    cart_id = serializers.IntegerField()
    order_type = serializers.ChoiceField(
        choices=Order.ORDER_TYPE_CHOICES, default="normal"
    )
    delivery_method = serializers.ChoiceField(
        choices=Order.DELIVERY_METHOD_CHOICES, default="delivery"
    )

    # Optional shipping data for delivery
    full_name = serializers.CharField(required=False, allow_blank=True)
    city_id = serializers.IntegerField(required=False)
    city = serializers.CharField(required=False, allow_blank=True)
    region_id = serializers.IntegerField(required=False)
    region = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)
    client_mobile2 = serializers.CharField(required=False, allow_blank=True)
    # Optional billing adjustments
    is_free_shipping = serializers.BooleanField(required=False, default=False)
    shipping_cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default="0.00"
    )
    discount_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default="0.00"
    )

    # For issue orders, link original order
    related_order_id = serializers.IntegerField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)

    # Optional: for admin creating orders on behalf of customer
    customer_id = serializers.IntegerField(required=False)
    coupon_code = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user

        cart_id = attrs["cart_id"]
        try:
            cart = Cart.objects.get(pk=cart_id, user__is_active=True)
        except Cart.DoesNotExist:
            raise serializers.ValidationError("Cart not found or invalid.")

        if cart.user != user and not user.is_admin:
            # only admin can create orders from someone else's cart
            raise serializers.ValidationError("You cannot use another user's cart.")

        order_type = attrs.get("order_type", "normal")

        # enforce who can create which order types
        admin_only_types = ["wholesale", "replacement", "exchange", "cancellation"]
        if (
            order_type in admin_only_types
            and not user.is_admin
            and not user.is_employee
        ):
            raise serializers.ValidationError(
                "You are not allowed to create this type of order."
            )

        attrs["cart"] = cart

        # validate related_order if provided
        related_order_id = attrs.get("related_order_id")
        if related_order_id:
            try:
                related_order = Order.objects.get(pk=related_order_id)
            except Order.DoesNotExist:
                raise serializers.ValidationError("Related order not found.")
            attrs["related_order"] = related_order
        else:
            attrs["related_order"] = None

        # choose customer for admin-created orders
        customer_id = attrs.get("customer_id")
        if customer_id:
            from accounts.models import User

            try:
                customer = User.objects.get(pk=customer_id, is_active=True)
            except User.DoesNotExist:
                raise serializers.ValidationError("Customer not found.")
            attrs["customer"] = customer
        else:
            attrs["customer"] = cart.user

        return attrs

    def create(self, validated_data):
        from .services import OrderService

        request = self.context["request"]
        user = request.user

        cart = validated_data["cart"]
        order_type = validated_data.get("order_type", "normal")
        delivery_method = validated_data.get("delivery_method", "delivery")
        related_order = validated_data.get("related_order", None)
        customer = validated_data.get("customer", cart.user)

        shipping_data = {
            "full_name": validated_data.get("full_name", ""),
            "city_id": validated_data.get("city_id", ""),
            "city": validated_data.get("city", ""),
            "region_id": validated_data.get("region_id", ""),
            "region": validated_data.get("region", ""),
            "location": validated_data.get("location", ""),
            "client_mobile2": validated_data.get("client_mobile2", ""),
        }
        coupon_code = validated_data.get("coupon_code") or None

        order = OrderService.create_from_cart(
            cart=cart,
            created_by=user,
            order_type=order_type,
            delivery_method=delivery_method,
            related_order=related_order,
            is_free_shipping=validated_data.get("is_free_shipping", False),
            shipping_cost=validated_data.get("shipping_cost"),
            extra_manual_discount=validated_data.get("discount_total", Decimal("0.00")),
            notes=validated_data.get("notes", ""),
            shipping_data=shipping_data,
            customer=customer,
            coupon_code=coupon_code,
        )

        return order
