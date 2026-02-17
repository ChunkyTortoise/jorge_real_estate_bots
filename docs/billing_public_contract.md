# Billing Public Contract (Transitional)

This document defines the current external contract used by API routes and tests.
It is intentionally explicit so compatibility shims can be removed in a controlled follow-up.

## SubscriptionService

`SubscriptionService` must expose these methods:
- `create_subscription(agency_id, plan_tier=None, payment_method_id=None, billing_interval="month", trial_days=None, price_id=None)`
- `upgrade_subscription(agency_id, new_plan_tier=None, billing_interval=None, new_price_id=None)`
- `cancel_subscription(agency_id, immediately=False, at_period_end=None)`
- `get_subscription_status(agency_id)`
- `add_payment_method(agency_id, payment_method_id)`

`get_subscription_status(agency_id)` payload:
- no subscription: `{ "status": "none", "is_active": false, "plan_tier": null }`
- active subscription: includes `status`, `is_active`, `plan_tier`, and `quota` with `used`, `total`, `remaining`

## QuotaManager

`QuotaManager` must expose these methods:
- `check_quota(agency_id, resource_type)`
- `record_usage(agency_id, resource_type, quantity=1, contact_id=None, bot_type=None, metadata=None)`
- `reset_quotas(agency_id=None)`
- `get_quota_limit(agency_id, resource_type)`

`get_usage_summary(agency_id)` payload must include:
- `has_subscription`, `quota`, `used`, `remaining`, `percentage_used`
- by-resource counters for legacy callers when usage rows exist (for example `lead`)

## Deprecation plan

These legacy compatibility methods/payloads should be versioned and removed only after:
1. API callers migrate to non-legacy equivalents.
2. Contract tests are updated for the new surface.
3. Release notes explicitly call out the breaking change.
