"""
Service layer: keeps business logic and external calls out of views.

Why this matters for team integration specifically -
The ML dev's model lives behind its own FastAPI endpoint. This file is the
ONLY place that knows about that endpoint's URL and payload shape. If their
request/response format changes mid-hackathon, you fix it here — nothing in
views.py has to change.
"""
import logging
from datetime import datetime, timezone

import requests
from django.conf import settings

from .models import Transaction, BehaviorBaseline, LedgerEntry

logger = logging.getLogger(__name__)

# Above this score, a transaction is paused and shown to the user.
# Tune this jointly with the ML dev once real scores start coming back.
RISK_THRESHOLD = 0.7


class ScoringServiceError(Exception):
    """Raised when the ML scoring service is unreachable or returns garbage."""


def get_or_create_baseline(user_id: str) -> BehaviorBaseline:
    """
    Fetch a user's behavioral baseline, or create a conservative default one.
    Mirrors the doc's 'cold-start' handling: new users default to a tighter,
    more cautious profile until real history accumulates.
    """
    baseline, _created = BehaviorBaseline.objects.get_or_create(
        user_id=user_id,
        defaults={
            "typical_recipients": [],
            "typical_amount_min": 0,
            "typical_amount_max": 50000,  # conservative default ceiling
            "typical_hours": list(range(7, 22)),  # 7am - 10pm
            "known_devices": [],
        },
    )
    return baseline


def call_ml_scoring_service(transaction: Transaction, baseline: BehaviorBaseline) -> dict:
    """
    Call the ML dev's FastAPI endpoint with transaction + baseline context.
    Expected response shape (agree this with the ML dev):
        {"risk_score": 0.0-1.0, "reason": "plain language explanation"}
    """
    payload = {
        "user_id": transaction.user_id,
        "recipient": transaction.recipient,
        "amount": float(transaction.amount),
        "device_id": transaction.device_id,
        "hour_of_day": datetime.now(timezone.utc).hour,
        "baseline": {
            "typical_recipients": baseline.typical_recipients,
            "typical_amount_min": float(baseline.typical_amount_min),
            "typical_amount_max": float(baseline.typical_amount_max),
            "typical_hours": baseline.typical_hours,
            "known_devices": baseline.known_devices,
        },
    }

    try:
        response = requests.post(
            settings.ML_SCORING_SERVICE_URL,
            json=payload,
            timeout=settings.ML_SERVICE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.error("ML scoring service call failed: %s", exc)
        raise ScoringServiceError(str(exc)) from exc

    if "risk_score" not in data:
        raise ScoringServiceError(f"Unexpected response shape from ML service: {data}")

    return data


def score_transaction(transaction: Transaction) -> Transaction:
    """
    Orchestrates: fetch baseline -> call ML service -> update transaction ->
    write to the transparency ledger. This is what the score endpoint calls.
    """
    baseline = get_or_create_baseline(transaction.user_id)

    try:
        result = call_ml_scoring_service(transaction, baseline)
        risk_score = float(result["risk_score"])
        reason = result.get("reason", "")
    except ScoringServiceError:
        # Fail-safe: if the ML service is down, don't silently approve a
        # real transaction. Flag conservatively and let the user/ops know.
        risk_score = 1.0
        reason = "Unable to verify this transaction automatically. Flagged for manual review."

    transaction.risk_score = risk_score
    transaction.risk_reason = reason
    transaction.scored_at = datetime.now(timezone.utc)
    transaction.status = (
        Transaction.Status.FLAGGED if risk_score >= RISK_THRESHOLD else Transaction.Status.APPROVED
    )
    transaction.save()

    LedgerEntry.objects.create(
        user_id=transaction.user_id,
        transaction=transaction,
        event_type="flagged" if transaction.status == Transaction.Status.FLAGGED else "scored",
        detail=f"risk_score={risk_score:.2f}; {reason}",
    )

    return transaction


def apply_user_decision(transaction: Transaction, decision: str) -> Transaction:
    """User responds to a flagged transaction: confirm anyway, or cancel."""
    if transaction.status != Transaction.Status.FLAGGED:
        raise ValueError("Only flagged transactions can be decided on.")

    transaction.status = (
        Transaction.Status.CONFIRMED if decision == "confirm" else Transaction.Status.CANCELLED
    )
    transaction.decided_at = datetime.now(timezone.utc)
    transaction.save()

    LedgerEntry.objects.create(
        user_id=transaction.user_id,
        transaction=transaction,
        event_type="overridden" if decision == "confirm" else "cancelled",
        detail=f"User chose to {decision} after being flagged.",
    )

    return transaction
