from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsAdminOrEmployee
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import (
    Product,
    ProductVariant,
    VariantOption,
    VariantOptionValue,
    ProductImage,
    Bundle,
    TieredPrice,
    BundleItem,
)
from .serializers import (
    ProductSerializer,
    ProductVariantSerializer,
    VariantOptionValueSerializer,
    BundleSerializer,
    TieredPriceSerializer,
    BundleItemSerializer,
)


# -----------------------------
# PRODUCT CRUD (Dashboard)
# -----------------------------
class DashboardProductListCreateView(generics.ListCreateAPIView):
    """
    GET: List all products for dashboard
    POST: Create a new product
    """

    queryset = Product.objects.prefetch_related("variants", "images")
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at"]
    authentication_classes = [JWTAuthentication]

    def perform_create(self, serializer):
        product = serializer.save()
        product.ensure_default_variant()


class DashboardProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE individual product
    """

    authentication_classes = [JWTAuthentication]
    queryset = Product.objects.prefetch_related("variants", "images")
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    lookup_field = "pk"


# -----------------------------
# PRODUCT VARIANT CRUD
# -----------------------------
class DashboardVariantListCreateView(generics.ListCreateAPIView):
    """
    Manage variants for products
    """

    queryset = ProductVariant.objects.select_related("product")
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        product_id = self.request.query_params.get("product")
        qs = self.queryset
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs


class DashboardVariantDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductVariant.objects.select_related("product")
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    authentication_classes = [JWTAuthentication]


# -----------------------------
# VARIANT OPTIONS & VALUES
# -----------------------------
class DashboardOptionValueListCreateView(generics.ListCreateAPIView):
    queryset = VariantOptionValue.objects.select_related("option")
    serializer_class = VariantOptionValueSerializer
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    authentication_classes = [JWTAuthentication]


class DashboardOptionValueDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = VariantOptionValue.objects.select_related("option")
    serializer_class = VariantOptionValueSerializer
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    authentication_classes = [JWTAuthentication]


# -----------------------------
# PRODUCT IMAGE CRUD
# -----------------------------
class DashboardProductImageListCreateView(generics.ListCreateAPIView):
    queryset = ProductImage.objects.select_related("product")
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    authentication_classes = [JWTAuthentication]

    def get_serializer_class(self):
        from rest_framework import serializers

        class ProductImageSerializer(serializers.ModelSerializer):
            class Meta:
                model = ProductImage
                fields = ["id", "product", "image", "alt_text"]

        return ProductImageSerializer


class DashboardProductImageDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductImage.objects.select_related("product")
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    authentication_classes = [JWTAuthentication]

    def get_serializer_class(self):
        from rest_framework import serializers

        class ProductImageSerializer(serializers.ModelSerializer):
            class Meta:
                model = ProductImage
                fields = ["id", "product", "image", "alt_text"]

        return ProductImageSerializer


# -----------------------------
# BUNDLE CRUD
# -----------------------------


class DashboardBundleListCreateView(generics.ListCreateAPIView):
    queryset = Bundle.objects.prefetch_related("items__variant__product")
    serializer_class = BundleSerializer  # you can later swap to a write serializer
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    authentication_classes = [JWTAuthentication]


class DashboardBundleDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Bundle.objects.prefetch_related("items__variant__product")
    serializer_class = BundleSerializer
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    authentication_classes = [JWTAuthentication]


class DashboardBundleItemListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    serializer_class = BundleItemSerializer

    def get_queryset(self):
        bundle_id = self.request.query_params.get("bundle")
        qs = BundleItem.objects.select_related("bundle", "variant", "variant__product")
        if bundle_id:
            qs = qs.filter(bundle_id=bundle_id)
        return qs


class DashboardBundleItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    serializer_class = BundleItemSerializer
    queryset = BundleItem.objects.select_related(
        "bundle", "variant", "variant__product"
    )


class DashboardTieredPriceListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    serializer_class = TieredPriceSerializer
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        variant_id = self.request.query_params.get("variant")
        qs = TieredPrice.objects.all()
        if variant_id:
            qs = qs.filter(variant_id=variant_id)
        return qs


class DashboardTieredPriceDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    authentication_classes = [JWTAuthentication]

    serializer_class = TieredPriceSerializer
    queryset = TieredPrice.objects.all()
