from django.db import models
from django.conf import settings
from decimal import Decimal
from orders.models import Order, OrderLine


class ReturnRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("in_transit", "Customer Shipped Back"),
        ("received", "Items Received"),
        ("refunded", "Refunded"),
        ("completed", "Completed"),
    ]

    RESOLUTION_CHOICES = [
        ("refund", "Refund"),
        ("exchange", "Exchange"),
        ("store_credit", "Store Credit"),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="return_requests",
    )
    original_order = models.ForeignKey(
        Order, on_delete=models.PROTECT, related_name="return_requests"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    resolution = models.CharField(
        max_length=20, choices=RESOLUTION_CHOICES, default="refund"
    )

    reason_general = models.TextField(blank=True)  # global note (optional)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # optional link to the issue orders that actually execute the stock/financial logic:
    return_issue_order = models.ForeignKey(
        Order,  # type 'cancellation' or 'exchange'
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_requests_as_return",
    )
    replacement_order = models.ForeignKey(
        Order,  # type 'replacement' or 'normal'
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_requests_as_replacement",
    )

    def __str__(self):
        return f"ReturnRequest #{self.pk} for Order {self.original_order.code}"


class ReturnRequestLine(models.Model):
    REASON_CHOICES = [
        ("size", "Wrong size"),
        ("color", "Did not like color"),
        ("damaged", "Damaged"),
        ("other", "Other"),
    ]

    return_request = models.ForeignKey(
        ReturnRequest, on_delete=models.CASCADE, related_name="lines"
    )
    order_line = models.ForeignKey(
        OrderLine, on_delete=models.PROTECT, related_name="return_lines"
    )

    requested_quantity = models.PositiveIntegerField()
    reason_code = models.CharField(
        max_length=20, choices=REASON_CHOICES, default="other"
    )
    reason_text = models.TextField(blank=True)  # free text

    def __str__(self):
        return f"{self.requested_quantity} of line {self.order_line_id} for return {self.return_request_id}"
