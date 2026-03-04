# Productization Continuation Checklist

## Milestone A: API/Auth Hardening
- [ ] Add role matrix for new `/api/*` productization endpoints.
- [ ] Enforce `admin/operator/viewer` authorization rules.
- [ ] Add explicit 403 tests for protected routes.

## Milestone B: Persistence Completion
- [ ] Add Alembic migration for `playbook_applications` table.
- [ ] Add Alembic migration for `roi_reports` table.
- [ ] Refactor playbook/report metadata persistence from file-only to DB-first.
- [ ] Add idempotency key support to `POST /api/playbooks/apply`.

## Milestone C: Testing
- [ ] Add integration test for onboarding bootstrap idempotency.
- [ ] Add integration test for `playbooks/apply` overwrite behavior.
- [ ] Add ROI boundary-window tests (`from`/`to` edge cases).
- [ ] Add report artifact retrieval integrity tests.

## Milestone D: Delivery Assets
- [ ] Add `scripts/smoke_productization.sh`.
- [ ] Add `docs/productization_api.md` with curl examples.
- [ ] Add `docs/client_onboarding_runbook.md`.
- [ ] Add `docs/release_checklist.md`.
