from decimal import Decimal
from django.utils import timezone
from .models import Discount
from catalog.models import ProductVariant


class DiscountApplicationResult:
    def __init__(
        self,
        cart,
        original_total,
        discounted_total,
        applied_discounts,
        total_discount,
        profit_before,
        profit_after,
    ):
        self.cart = cart
        self.original_total = original_total
        self.discounted_total = discounted_total
        self.applied_discounts = applied_discounts  # list of dicts
        self.total_discount = total_discount
        self.profit_before = profit_before
        self.profit_after = profit_after


class DiscountEngine:
    GLOBAL_MAX_PROFIT_SHARE = Decimal("0.25")  # hard cap: no more than 25% of profit

    @classmethod
    def _compute_cart_totals_and_profit(cls, cart):
        """
        Compute:
        - original_total: sum of line prices (unit_price * qty)
        - cost_total: sum of cost_price * qty (using variant cost_price)
        """
        original_total = Decimal("0")
        cost_total = Decimal("0")

        for item in cart.items.select_related("variant"):
            line_total = item.unit_price * item.quantity
            original_total += line_total
            if item.variant:
                cost_total += item.variant.cost_price * item.quantity
            # For bundles, you could approximate cost from bundle composition if needed.

        profit = max(original_total - cost_total, Decimal("0"))
        return original_total, cost_total, profit

    @classmethod
    def _eligible_discounts(cls, cart, coupon_code=None):
        now = timezone.now()
        discounts = Discount.objects.all()
        eligible = []

        for d in discounts:
            if not d.is_currently_active():
                continue

            # Coupon constraint
            if d.discount_type == "coupon":
                if not coupon_code or d.code.lower() != coupon_code.lower():
                    continue

            # Cart subtotal condition (based on current cart, pre-discount)
            original_total, _, _ = cls._compute_cart_totals_and_profit(cart)
            if d.min_cart_subtotal is not None and original_total < d.min_cart_subtotal:
                continue

            # Abandoned cart condition: cart not updated for >= min_abandoned_minutes
            if (
                d.discount_type == "abandoned_cart"
                and d.min_abandoned_minutes is not None
            ):
                if not cart.updated_at:
                    continue
                idle_minutes = (now - cart.updated_at).total_seconds() / 60
                if idle_minutes < d.min_abandoned_minutes:
                    continue

            eligible.append(d)

        # Sort by priority (lower first)
        eligible.sort(key=lambda disc: disc.priority)
        return eligible

    @classmethod
    def apply_discounts(cls, cart, coupon_code=None):
        """
        Returns DiscountApplicationResult.
        Does NOT modify cart or prices; it's a pure calculator.
        """
        original_total, cost_total, profit_before = cls._compute_cart_totals_and_profit(
            cart
        )
        if profit_before <= 0:
            # No profit → do not allow any discount that would create a loss
            return DiscountApplicationResult(
                cart,
                original_total,
                original_total,
                [],
                Decimal("0"),
                profit_before,
                profit_before,
            )

        global_max_discount = profit_before * cls.GLOBAL_MAX_PROFIT_SHARE
        global_discount_used = Decimal("0")

        discounts = cls._eligible_discounts(cart, coupon_code)
        applied_discounts = []

        current_total = original_total

        for d in discounts:
            # Compute maximum this discount is allowed to eat from profit
            disc_max_for_this = profit_before * min(
                d.max_profit_share, cls.GLOBAL_MAX_PROFIT_SHARE
            )
            remaining_global_room = global_max_discount - global_discount_used
            if remaining_global_room <= 0:
                break  # can't apply any more discounts

            allowed_for_this = min(disc_max_for_this, remaining_global_room)
            if allowed_for_this <= 0:
                continue

            # Rough calculation of discount amount based on type
            discount_amount = cls._calculate_discount_amount(d, cart, current_total)

            # Cap by allowed_for_this
            discount_amount = min(discount_amount, allowed_for_this)

            if discount_amount <= 0:
                continue

            # Apply
            current_total -= discount_amount
            global_discount_used += discount_amount
            applied_discounts.append(
                {
                    "id": d.id,
                    "name": d.name,
                    "type": d.discount_type,
                    "value_type": d.value_type,
                    "value": str(d.value),
                    "applied_amount": str(discount_amount),
                    "priority": d.priority,
                }
            )

            # Exclusive discount stops further processing
            if d.exclusive:
                break
            # If not stackable, we ignore lower-priority discounts
            if not d.stackable:
                break

        profit_after = max(current_total - cost_total, Decimal("0"))

        return DiscountApplicationResult(
            cart=cart,
            original_total=original_total,
            discounted_total=max(current_total, Decimal("0")),
            applied_discounts=applied_discounts,
            total_discount=global_discount_used,
            profit_before=profit_before,
            profit_after=profit_after,
        )

    @classmethod
    def _calculate_discount_amount(
        cls, discount: Discount, cart, current_total: Decimal
    ) -> Decimal:
        """
        Calculate the raw discount amount BEFORE profit caps.
        """
        amount = Decimal("0")

        # Product-level override and flash sale:
        if discount.discount_type in ("product_override", "flash_sale"):
            # Only for targeted variants or all variants
            for item in cart.items.select_related("variant"):
                if not item.variant:
                    continue
                if (
                    discount.target_variants.exists()
                    and item.variant not in discount.target_variants.all()
                ):
                    continue
                # override price if given, otherwise apply percent/fixed per line
                if discount.override_price is not None:
                    original_line_total = item.unit_price * item.quantity
                    new_line_total = discount.override_price * item.quantity
                    line_discount = max(
                        original_line_total - new_line_total, Decimal("0")
                    )
                else:
                    # fallback to generic value/percent on line price
                    original_line_total = item.unit_price * item.quantity
                    if discount.value_type == "percent":
                        line_discount = (
                            original_line_total * discount.value
                        ) / Decimal("100")
                    else:
                        line_discount = min(
                            discount.value * item.quantity, original_line_total
                        )
                amount += line_discount

        # Cart subtotal discounts (and coupons, abandoned_cart acting on cart total)
        elif discount.discount_type in ("cart_subtotal", "coupon", "abandoned_cart"):
            if discount.value_type == "percent":
                amount = (current_total * discount.value) / Decimal("100")
            else:
                amount = min(discount.value, current_total)

        return max(amount, Decimal("0"))
