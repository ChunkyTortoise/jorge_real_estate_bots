"""Billing domain types and exports."""

from __future__ import annotations

from enum import Enum


class PlanTier(str, Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


PLAN_QUOTAS: dict[str, int] = {
    PlanTier.STARTER.value: 100,
    PlanTier.PROFESSIONAL.value: 500,
    PlanTier.ENTERPRISE.value: 999999,
}


__all__ = [
    "PlanTier",
    "SubscriptionStatus",
    "PLAN_QUOTAS",
]
