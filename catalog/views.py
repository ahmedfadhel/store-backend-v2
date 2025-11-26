from rest_framework import generics, filters
from django.db.models import Q, Min, Max
from .models import Product, ProductVariant, Bundle, VariantOptionValue
from .serializers import ProductSerializer, ProductVariantSerializer, BundleSerializer


# -----------------------------
# PRODUCT LIST / DETAIL
# -----------------------------
class ProductListView(generics.ListAPIView):
    """
    List all products with optional filters:
    - ?color=red
    - ?min_price=10&max_price=50
    - ?in_stock=true
    """

    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).prefetch_related(
            "variants__options", "variants", "images"
        )

        color = self.request.query_params.get("color")
        min_price = self.request.query_params.get("min_price")
        max_price = self.request.query_params.get("max_price")
        in_stock = self.request.query_params.get("in_stock")

        if color:
            queryset = queryset.filter(
                variants__options__option__name__iexact="color",
                variants__options__value__iexact=color,
            )

        if min_price:
            queryset = queryset.filter(variants__sale_price__gte=min_price)

        if max_price:
            queryset = queryset.filter(variants__sale_price__lte=max_price)

        if in_stock and in_stock.lower() == "true":
            queryset = queryset.filter(variants__stock__gt=0)

        return queryset.distinct()


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer
    lookup_field = "slug"
    lookup_url_kwarg = "slug"
    # slug_field = "slug"
    queryset = Product.objects.prefetch_related(
        "variants__options", "images", "variants"
    )


# -----------------------------
# VARIANT LIST (flattened for quick access)
# -----------------------------
class VariantListView(generics.ListAPIView):
    """
    Flattened list of all product variants (for admin or filters)
    """

    serializer_class = ProductVariantSerializer
    queryset = ProductVariant.objects.select_related("product").prefetch_related(
        "options"
    )


# -----------------------------
# BUNDLES
# -----------------------------
class BundleListView(generics.ListAPIView):
    serializer_class = BundleSerializer
    queryset = Bundle.objects.prefetch_related("items__variant__product")


class BundleDetailView(generics.RetrieveAPIView):
    serializer_class = BundleSerializer
    queryset = Bundle.objects.prefetch_related("items__variant__product")
