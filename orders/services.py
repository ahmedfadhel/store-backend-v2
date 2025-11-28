# orders/services.py

from decimal import Decimal
from django.db import transaction
from django.utils.crypto import get_random_string
from django.db.models import F

from carts.models import Cart, CartItem
from orders.models import Order, OrderLine
from catalog.models import ProductVariant, Bundle


def generate_order_code() -> str:
    # You can make this more fancy with dates, etc.
    return "ORD-" + get_random_string(10).upper()


class OrderService:

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
        discount_total: Decimal = Decimal("0"),
        notes: str = "",
        customer: None | object = None,
    ) -> Order:
        """
        Convert a cart into an order.

        - Supports normal and admin-only order types.
        - Handles variant & bundle lines.
        - Decrements stock for non-issue orders.
        """

        if customer is None:
            customer = cart.user

        # 1) Create order skeleton
        order = Order.objects.create(
            code=generate_order_code(),
            customer=customer,
            created_by=created_by,
            order_type=order_type,
            delivery_method=delivery_method,
            related_order=related_order,
            is_free_shipping=is_free_shipping,
            shipping_cost=Decimal("0") if is_free_shipping else shipping_cost,
            discount_total=discount_total,
            shipping_name=(shipping_data or {}).get("shipping_name", ""),
            shipping_address=(shipping_data or {}).get("shipping_address", ""),
            shipping_city=(shipping_data or {}).get("shipping_city", ""),
            shipping_postal_code=(shipping_data or {}).get("shipping_postal_code", ""),
            shipping_country=(shipping_data or {}).get("shipping_country", ""),
            notes=notes,
        )

        items_total = Decimal("0")

        # 2) Copy cart items → order lines
        for cart_item in cart.items.select_related("variant", "bundle"):
            if cart_item.line_type == "variant":
                variant = cart_item.variant
                unit_price = cart_item.unit_price
                quantity = cart_item.quantity

                OrderLine.objects.create(
                    order=order,
                    line_type="variant",
                    variant=variant,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=unit_price * quantity,
                    product_name=str(variant),
                )

                items_total += unit_price * quantity

                # Decrement stock for non-issue orders
                if order_type == "normal" or order_type == "wholesale":
                    ProductVariant.objects.filter(pk=variant.pk).update(
                        stock=F("stock") - quantity
                    )

            elif cart_item.line_type == "bundle":
                bundle = cart_item.bundle
                unit_price = cart_item.unit_price
                quantity = cart_item.quantity

                OrderLine.objects.create(
                    order=order,
                    line_type="bundle",
                    bundle=bundle,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=unit_price * quantity,
                    bundle_name=bundle.name,
                )

                items_total += unit_price * quantity

                # Decrement stock for non-issue orders by bundle composition
                if order_type == "normal" or order_type == "wholesale":
                    for bi in bundle.items.select_related("variant"):
                        ProductVariant.objects.filter(pk=bi.variant.pk).update(
                            stock=F("stock") - (bi.quantity * quantity)
                        )

        # 3) Set totals & save
        order.items_total = items_total
        order.grand_total = (
            order.items_total + order.shipping_cost - order.discount_total
        )
        order.save()

        # 4) Mark cart as converted (you can also delete items if you want)
        cart.is_converted = True
        cart.save(update_fields=["is_converted"])

        return order
