# returns/views.py

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from returns.models import ReturnRequest
from returns.serializers import (
    ReturnRequestSerializer,
    ReturnRequestCreateSerializer,
)
from accounts.permissions import IsAdminOrEmployee


class ReturnRequestListCreateView(generics.ListCreateAPIView):
    """
    GET:
      - Customer: list only their own return requests
      - Admin/Employee: list all return requests

    POST:
      - Customer: create a new return request for their own order
      - Admin: can also create return requests manually if needed
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = ReturnRequest.objects.select_related(
            "customer", "original_order"
        ).prefetch_related("lines__order_line")
        if getattr(user, "is_admin", False) or getattr(user, "is_employee", False):
            return qs
        return qs.filter(customer=user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ReturnRequestCreateSerializer
        return ReturnRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        read_serializer = ReturnRequestSerializer(instance)
        headers = self.get_success_headers(read_serializer.data)
        return Response(
            read_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class ReturnRequestDetailView(generics.RetrieveUpdateAPIView):
    """
    GET:
      - Customer: can view only their own return requests
      - Admin/Employee: can view any

    PATCH:
      - Admin/Employee: can update status, resolution, and link issue/replacement orders.
      - Customers cannot modify after creation (you can relax this if you want).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ReturnRequestSerializer

    def get_queryset(self):
        user = self.request.user
        qs = ReturnRequest.objects.select_related(
            "customer", "original_order", "return_issue_order", "replacement_order"
        ).prefetch_related("lines__order_line")
        if getattr(user, "is_admin", False) or getattr(user, "is_employee", False):
            return qs
        return qs.filter(customer=user)

    def partial_update(self, request, *args, **kwargs):
        user = request.user
        # only admin/employee can update return request (status / linking orders)
        if not (
            getattr(user, "is_admin", False) or getattr(user, "is_employee", False)
        ):
            return Response(
                {"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN
            )

        # Allow admin to update subset of fields
        instance = self.get_object()
        data = request.data.copy()

        # We can restrict allowed fields for PATCH
        allowed_fields = {
            "status",
            "resolution",
            "return_issue_order",
            "replacement_order",
            "reason_general",
        }
        data = {k: v for k, v in data.items() if k in allowed_fields}

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
