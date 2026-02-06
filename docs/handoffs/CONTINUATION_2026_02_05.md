# Continuation Prompt: jorge_real_estate_bots

**Date**: February 5, 2026
**Repo**: `ChunkyTortoise/jorge_real_estate_bots` (private)
**Local**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots`
**Branch**: `main` (PR #1 merged)
**Parent**: EnterpriseHub at `/Users/cave/Documents/GitHub/EnterpriseHub`

---

## What Was Done (Phase 1 — Complete)

7 atomic commits merged via PR #1:

1. **Buyer bot** — `JorgeBuyerBot` with state progression, temperature scoring, property matching, FastAPI routes
2. **Database layer** — PostgreSQL async models (Lead, Contact, Conversation, Property), SQLAlchemy + Alembic migration, repository pattern
3. **Mock→real queries** — Replaced `_fetch_real_conversation_data` (delegated to `_fetch_active_conversations`), deleted `_generate_realistic_conversation` (~104 lines), replaced `_calculate_real_lead_source_roi` with `JorgeBusinessRules.calculate_commission()` + deterministic cost map, added `metadata_json` to commission analysis query, removed stale TODO
4. **Dashboard v3** — 20+ modular Streamlit components, archived legacy dashboards, auth middleware, event broker, WebSocket
5. **Test fixes** — Fixed `TestSellerBotEdgeCases` AsyncMock fixture (3 of 4 pass), added buyer/smoke/mobile tests (279 total, 256 pass)
6. **Docker** — Dockerfile, docker-compose (PostgreSQL + Redis), .dockerignore, Locust load testing
7. **Docs** — Relocated 30+ root artifacts to `docs/phases/`, `docs/handoffs/`, `docs/reference/`

Also fixed: Python 3.14 regex incompatibility in `bots/shared/logger.py` (double-escaped backslashes in raw strings).

---

## What Needs Doing Next (Priority Order)

### CRITICAL — Security

1. **Remove `.env` from git tracking and history**
   ```bash
   cd /Users/cave/Documents/GitHub/jorge_real_estate_bots
   git rm --cached .env
   # Add .env to .gitignore (already there, but verify)
   git commit -m "fix: remove .env from tracking"
   git push
   # Then: git filter-repo or BFG to scrub .env from history
   # Then: ROTATE ALL SECRETS in the .env file
   ```

2. **Remove 24 `__pycache__/*.pyc` files from tracking**
   ```bash
   git rm -r --cached '**/__pycache__'
   git commit -m "chore: untrack __pycache__ files"
   git push
   ```

### HIGH — Bug Fixes

3. **Fix `_get_fallback_conversations()` signature mismatch**
   - **File**: `bots/shared/dashboard_data_service.py`
   - **Problem**: Method defined as `_get_fallback_conversations(self)` but called with `(self, filters, page, page_size)` at line ~396 and ~472
   - **Fix**: Add `filters, page, page_size` parameters to match callers

4. **Replace hardcoded `admin123` password**
   - **File**: `bots/shared/auth_service.py:110`
   - **Fix**: Generate random password, force change on first login

### MEDIUM — Remaining Mock Data (Phase 2)

5. **`_fetch_lead_data_for_budget_analysis()`** — `bots/shared/metrics_service.py` ~line 450
   - Currently uses `import random` to generate 60 simulated leads
   - Replace with real SQLAlchemy query against `LeadModel` (same pattern as `_fetch_lead_data_for_commission_analysis`)

6. **`_fetch_lead_data_for_timeline_analysis()`** — `bots/shared/metrics_service.py` ~line 588
   - Uses random to assign timeline classifications
   - Replace: query `LeadModel.metadata_json` for timeline data, or derive from `created_at`

7. **`_generate_commission_trend_data()`** — `bots/shared/metrics_service.py` ~line 763
   - Uses random to generate trend amounts
   - Replace: aggregate `LeadModel` by month for last 4 months

8. **`_calculate_conversation_summary()`** — `bots/shared/dashboard_data_service.py` ~line 538
   - Returns hardcoded dict with fake stage/temperature counts
   - Replace: aggregate from `ConversationModel`

### LOW — Test Infrastructure

9. **Set up test PostgreSQL** — Either:
   - `docker-compose up -d postgres` before test runs, OR
   - Use SQLite in-memory with `AsyncSessionFactory` override for tests
   - This would fix the remaining 23 failing tests

10. **Delete remote feature branch**
    ```bash
    git push origin --delete feature/integrate-production-phase1
    ```

---

## Key Files to Read First

| File | Why |
|------|-----|
| `bots/shared/metrics_service.py` | Has 3 remaining mock methods to replace |
| `bots/shared/dashboard_data_service.py` | Has fallback signature bug + 1 mock method |
| `bots/shared/auth_service.py` | Hardcoded password at line 110 |
| `database/models.py` | LeadModel, ContactModel, ConversationModel schemas |
| `database/repository.py` | Existing upsert patterns to follow |
| `tests/test_jorge_seller_bot.py` | Fixed fixture pattern (reference for future tests) |
| `.env` | Needs removal from git — contains secrets |

---

## Test Results (as of Feb 5, 2026)

- **256 PASS** — All unit tests for buyer bot, dashboard components, models, business rules, etc.
- **23 FAIL** — All caused by `role "postgres" does not exist` (no local PostgreSQL)
- **0 FAIL** from code changes — all failures are pre-existing infrastructure issues

### Fixed by our changes:
- `TestSellerBotEdgeCases::test_out_of_order_responses` — was TypeError, now PASS
- `TestSellerBotEdgeCases::test_ambiguous_responses` — was TypeError, now PASS
- `TestSellerBotEdgeCases::test_concurrent_conversations` — was TypeError, now PASS
- `TestSellerBotEdgeCases::test_extremely_high_price_expectation` — still FAIL (needs PostgreSQL for `save_conversation_state`)

---

## Architecture Quick Reference

```
jorge_real_estate_bots/
├── bots/
│   ├── buyer_bot/          # NEW: JorgeBuyerBot
│   ├── lead_bot/           # LeadAnalyzer + WebSocket
│   ├── seller_bot/         # JorgeSellerBot (Q1-Q4)
│   └── shared/             # Services, models, config
│       ├── metrics_service.py      # 3 mock methods remaining
│       ├── dashboard_data_service.py # 1 mock + fallback bug
│       ├── business_rules.py       # JorgeBusinessRules (reuse)
│       └── auth_service.py         # admin123 password
├── command_center/
│   ├── components/         # 20+ Streamlit components
│   └── dashboard_v3.py     # Main dashboard
├── database/
│   ├── models.py           # SQLAlchemy async models
│   ├── repository.py       # Upsert operations
│   └── session.py          # AsyncSessionFactory
├── tests/                  # 279 tests
├── Dockerfile + docker-compose.yml
└── docs/{phases,handoffs,reference}/
```
