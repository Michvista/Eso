import uuid
from django.db import models


class BehaviorBaseline(models.Model):
    """
    A user's learned 'normal' — typical recipients, amount range, timing.
    Updated automatically when transfers are approved or user-confirmed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, unique=True)
    typical_recipients = models.JSONField(default=list)  # list of recipient ids/names
    typical_amount_min = models.DecimalField(max_digits=14, decimal_places=2)
    typical_amount_max = models.DecimalField(max_digits=14, decimal_places=2)
    typical_hours = models.JSONField(default=list)  # e.g. [8,9,10,...,21]
    known_devices = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Baseline for {self.user_id}"


class Transaction(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        FLAGGED = "flagged", "Flagged"
        CANCELLED = "cancelled", "Cancelled"
        CONFIRMED = "confirmed", "Confirmed after flag"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100)
    recipient = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    device_id = models.CharField(max_length=150, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    risk_score = models.FloatField(null=True, blank=True)
    risk_reason = models.TextField(blank=True)  # plain-language explanation
    created_at = models.DateTimeField(auto_now_add=True)
    scored_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user_id} -> {self.recipient} ({self.amount})"


class LedgerEntry(models.Model):
    """
    Append-only transparency log. Every score, flag, and user decision
    gets written here so it can be rendered in the activity/trust log UI.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100)
    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="ledger_entries"
    )
    event_type = models.CharField(max_length=50)  # e.g. "scored", "flagged", "overridden"
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} @ {self.created_at}"
