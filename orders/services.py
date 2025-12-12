# orders/services.py

from decimal import Decimal
from django.db import transaction
from django.utils.crypto import get_random_string
from django.db.models import F

from carts.models import Cart, CartItem
from orders.models import Order, OrderLine
from catalog.models import ProductVariant, Bundle
from discounts.engine import DiscountEngine
from accounts.models import ShippingAddress


def generate_order_code() -> str:
    # You can make this more fancy with dates, etc.
    return "ORD-" + get_random_string(10).upper()


class OrderService:

    @staticmethod
    def _get_or_update_shipping_profile(
        customer, shipping_data: dict | None
    ) -> ShippingAddress:
        """
        - If shipping_data provided: create/update the customer's profile and return it.
        - If not provided: use existing profile; raise if no valid shipping info.
        """
        profile = getattr(customer, "profile", None)
        if shipping_data and any(shipping_data.values()):
            # ensure profile exists
            if profile is None:
                profile = ShippingAddress.objects.create(user=customer)

            # update fields from payload (if given)
            for field in [
                "full_name",
                "city_id",
                "city",
                "region_id",
                "region",
                "location",
                "client_mobile2",
            ]:
                if field in shipping_data and shipping_data[field] is not None:
                    setattr(profile, field, shipping_data[field])

            # also keep full_name in sync if provided
            if "full_name" in shipping_data and shipping_data["full_name"]:
                profile.full_name = shipping_data["full_name"]

            profile.save()
        else:
            # no new data: must have existing profile with valid shipping info
            if profile is None or not profile.has_shipping_info():
                raise ValueError(
                    "Shipping information is missing. Please provide it once to your profile."
                )

        return profile

    @staticmethod
    @transaction.atomic
    def create_from_cart(
        *,
        cart: Cart,
        created_by,
        order_type: str = "normal",
        delivery_method: str = "delivery",
        shipping_data: dict | None = None,
        related_order: Order | None = None,
        is_free_shipping: bool = False,
        shipping_cost: Decimal = Decimal("0"),
        # this becomes "manual extra discount" (admin override, loyalty, etc.)
        extra_manual_discount: Decimal = Decimal("0"),  # optional admin override
        notes: str = "",
        customer: None | object = None,
        coupon_code: str | None = None,  # << NEW
    ) -> Order:
        """
        Convert a cart into an order.

        - Supports normal and admin-only order types.
        - Handles variant & bundle lines.
        - Decrements stock for non-issue orders.
        """

        if customer is None:
            customer = cart.user

        # 1) Ensure shipping profile exists and is up to date
        #    (except maybe pickup orders; you can relax this if you want)
        profile = None
        if delivery_method == "delivery":
            profile = OrderService._get_or_update_shipping_profile(
                customer, shipping_data or {}
            )
        else:
            # pickup: profile is optional, but still updated if shipping_data provided
            if shipping_data and any(shipping_data.values()):
                profile = OrderService._get_or_update_shipping_profile(
                    customer, shipping_data or {}
                )
            else:
                profile = getattr(customer, "profile", None)

        # 1) Run discount engine once for revenue orders
        engine_result = None
        if order_type in ("normal", "wholesale"):
            engine_result = DiscountEngine.apply_discounts(
                cart, coupon_code=coupon_code
            )
        else:
            # For issue-related orders we typically don't apply marketing discounts
            engine_result = None

        if engine_result:
            original_total = engine_result.original_total
            engine_discount_total = engine_result.total_discount
            discounted_total = engine_result.discounted_total
            profit_before = engine_result.profit_before
            profit_after = engine_result.profit_after
            applied_discounts = engine_result.applied_discounts
        else:
            # No discounts (or issue order) → compute basic total & profit
            original_total = Decimal("0")
            cost_total = Decimal("0")
            for item in cart.items.select_related("variant"):
                original_total += item.unit_price * item.quantity
                if item.variant:
                    cost_total += item.variant.cost_price * item.quantity
            profit_before = max(original_total - cost_total, Decimal("0"))
            profit_after = profit_before
            discounted_total = original_total
            engine_discount_total = Decimal("0")
            applied_discounts = []
        # 2) Add optional manual discount (e.g. admin override or loyalty)
        extra_manual_discount = max(extra_manual_discount, Decimal("0"))

        if extra_manual_discount > discounted_total:
            extra_manual_discount = discounted_total

        total_discount = engine_discount_total + extra_manual_discount
        items_total_after_all_discounts = discounted_total - extra_manual_discount
        # 3) Prepare shipping snapshot from profile (if any)
        shipping_kwargs = {}
        if profile:
            shipping_kwargs.update(
                shipping_profile=profile,
                full_name=profile.full_name or profile.full_name or "",
                city_id=profile.city_id or "",
                city=profile.city or "",
                region_id=profile.region_id or "",
                region=profile.region or "",
                location=profile.location or "",
                client_mobile2=profile.client_mobile2 or "",
            )
        else:
            shipping_kwargs.update(
                shipping_profile=None,
                shipping_name="",
                shipping_address="",
                shipping_city="",
                shipping_postal_code="",
                shipping_country="",
                shipping_phone="",
            )
        # 3) Create order skeleton
        # 3) Create Order skeleton (lines come after)
        order = Order.objects.create(
            code=generate_order_code(),
            customer=customer,
            created_by=created_by,
            order_type=order_type,
            delivery_method=delivery_method,
            related_order=related_order,
            is_free_shipping=is_free_shipping,
            shipping_cost=Decimal("0") if is_free_shipping else shipping_cost,
            # Totals snapshot
            items_total=original_total,  # BEFORE all discounts
            discount_total=total_discount,  # engine + manual
            grand_total=Decimal("0"),  # set below after lines
            # Discount engine details
            discount_breakdown=(
                {
                    "applied_discounts": applied_discounts,
                    "engine_discount_total": str(engine_discount_total),
                    "extra_manual_discount": str(extra_manual_discount),
                    "coupon_code": coupon_code,
                }
                if applied_discounts or extra_manual_discount
                else None
            ),
            profit_before_discounts=profit_before,
            profit_after_discounts=profit_after,
            # shipping_info=customer.ShippingAddres,
            notes=notes,
            **shipping_kwargs,
        )
        # 4) Copy CartItems → OrderLines and adjust stock
        for cart_item in cart.items.select_related("variant", "bundle"):
            if cart_item.line_type == "variant":
                variant = cart_item.variant
                unit_price = cart_item.unit_price  # original unit price
                qty = cart_item.quantity

                OrderLine.objects.create(
                    order=order,
                    line_type="variant",
                    variant=variant,
                    quantity=qty,
                    unit_price=unit_price,
                    subtotal=unit_price * qty,  # subtotal BEFORE discounts
                    product_name=str(variant),
                )

                if order_type in ("normal", "wholesale"):
                    ProductVariant.objects.filter(pk=variant.pk).update(
                        stock=F("stock") - qty
                    )

            elif cart_item.line_type == "bundle":
                bundle = cart_item.bundle
                unit_price = cart_item.unit_price
                qty = cart_item.quantity

                OrderLine.objects.create(
                    order=order,
                    line_type="bundle",
                    bundle=bundle,
                    quantity=qty,
                    unit_price=unit_price,
                    subtotal=unit_price * qty,
                    bundle_name=bundle.name,
                )

                if order_type in ("normal", "wholesale"):
                    for bi in bundle.items.select_related("variant"):
                        ProductVariant.objects.filter(pk=bi.variant.pk).update(
                            stock=F("stock") - (bi.quantity * qty)
                        )
        # 5) Finalize grand_total (items after discounts + shipping)
        order.grand_total = items_total_after_all_discounts + order.shipping_cost
        order.save(
            update_fields=[
                "discount_total",
                "grand_total",
                "discount_breakdown",
                "profit_before_discounts",
                "profit_after_discounts",
                "shipping_profile",
                "city_id",
                "city",
                "region_id",
                "region",
                "location",
                "full_name",
                "client_mobile2",
            ]
        )

        # 6) Mark cart converted
        cart.is_converted = True
        cart.save(update_fields=["is_converted"])

        return order
