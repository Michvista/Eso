from rest_framework import serializers
from .models import Transaction, BehaviorBaseline, LedgerEntry


class BehaviorBaselineSerializer(serializers.ModelSerializer):
    class Meta:
        model = BehaviorBaseline
        fields = [
            "user_id",
            "typical_recipients",
            "typical_amount_min",
            "typical_amount_max",
            "typical_hours",
            "known_devices",
            "updated_at",
        ]


class TransactionCreateSerializer(serializers.ModelSerializer):
    """
    What the frontend sends when a user initiates a transfer.
    user_id is deliberately NOT accepted from the client — it's set server-side
    from the authenticated request user in the view. Otherwise anyone with a
    valid token could submit transactions under someone else's user_id.
    """

    class Meta:
        model = Transaction
        fields = ["id", "recipient", "amount", "device_id"]
        read_only_fields = ["id"]


class TransactionSerializer(serializers.ModelSerializer):
    """Full transaction state, including scoring outcome — used in responses."""

    class Meta:
        model = Transaction
        fields = [
            "id",
            "user_id",
            "recipient",
            "amount",
            "device_id",
            "status",
            "risk_score",
            "risk_reason",
            "created_at",
            "scored_at",
            "decided_at",
        ]
        read_only_fields = fields


class TransactionDecisionSerializer(serializers.Serializer):
    """What the frontend sends when the user responds to a flagged transaction."""

    decision = serializers.ChoiceField(choices=["confirm", "cancel"])


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ["id", "transaction", "event_type", "detail", "created_at"]
