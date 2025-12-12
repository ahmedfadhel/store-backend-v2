from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DiscountViewSet, ApplyDiscountsView

router = DefaultRouter()
router.register("admin", DiscountViewSet, basename="discount")

urlpatterns = [
    path("", include(router.urls)),
    path("apply/", ApplyDiscountsView.as_view(), name="discount-apply"),
]
