from decimal import Decimal
from .models import ProductVariant, TieredPrice


def resolve_price(
    variant: ProductVariant,
    *,
    quantity: Decimal | None = None,
    weight: Decimal | None = None
):
    """
    Returns (sale_price, basis_used, tier_id or None) for the given variant and requested measure.
    - If variant.pricing_mode == 'flat': returns variant.sale_price, None, None
    - If 'tiered': chooses the matching TieredPrice row by basis/range.
    """
    if variant.pricing_mode == "flat" or not variant.tiers.exists():
        return (variant.sale_price, None, None)

    # Prefer matching basis by what caller provided
    candidates: list[TieredPrice] = []
    if quantity is not None:
        candidates += list(variant.tiers.filter(basis="quantity"))
    if weight is not None:
        candidates += list(variant.tiers.filter(basis="weight"))

    # If caller didn’t pass anything, default to the minimal tier (for “starts from” display)
    if not candidates:
        tp = variant.tiers.order_by("sale_price", "min_value").first()
        return (
            (tp.sale_price, tp.basis, tp.id) if tp else (variant.sale_price, None, None)
        )

    # Try to match range
    for tp in sorted(candidates, key=lambda x: (x.min_value, x.sale_price)):
        if tp.matches(qty=quantity, weight=weight):
            return (tp.sale_price, tp.basis, tp.id)

    # Fallback: nearest (smallest min_value) among the chosen basis set
    tp = sorted(candidates, key=lambda x: (x.min_value, x.sale_price))[0]
    return (tp.sale_price, tp.basis, tp.id)
