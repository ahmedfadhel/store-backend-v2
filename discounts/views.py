from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Discount
from .serializers import DiscountSerializer
from .engine import DiscountEngine
from carts.models import Cart
from accounts.permissions import IsAdminOrEmployee
from rest_framework.views import APIView
from .serializers import ApplyDiscountRequestSerializer, DiscountedCartSerializer


class DiscountViewSet(viewsets.ModelViewSet):
    """
    Admin-only CRUD for discounts.
    """

    queryset = Discount.objects.all().order_by("priority", "-created_at")
    serializer_class = DiscountSerializer
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]


class ApplyDiscountsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_serializer = ApplyDiscountRequestSerializer(
            data=request.data, context={"request": request}
        )
        req_serializer.is_valid(raise_exception=True)
        result = req_serializer.save()
        res_serializer = DiscountedCartSerializer.from_result(result)
        return Response(res_serializer.data, status=status.HTTP_200_OK)
