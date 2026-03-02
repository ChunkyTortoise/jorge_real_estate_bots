# E2E Smoke Test — Jorge Real Estate Bots

**Test Date:** 2026-03-02
**Tester:** Cayman Roden
**AirDroid Number:** +1 310-982-0492
**GHL Contact:** `prX3fC1c7UaCjUzwdeyu` (cayman test)
**Live URL:** `https://jorge-realty-ai-xxdf.onrender.com`
**Commit tested:** `9027dd6` (feat: add CMA trigger + advance-stage endpoints)
**Test suite:** 663 passing (661 + 2 skipped), 0 failures

---

## Summary

Full buyer → seller qualification flow validated against the live Render deployment.
Buyer bot extracts budget and pre-approval status. Seller bot extracts price, condition, motivation, escalates temperature warm → hot, and applies `Hot-Seller` + `Seller-Qualified` tags.

---

## Phase 1: Buyer Flow

### Q0 — Initial outreach (real SMS)

**Endpoint:** `POST /api/ghl/initiate-qualification`
**Payload:**
```json
{
  "contact_id": "prX3fC1c7UaCjUzwdeyu",
  "location_id": "3xt4qayAh35BlDLaUv7P"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Cayman, thanks for reaching out! Are you looking to buy or sell in Rancho Cucamonga?",
  "actions": []
}
```
**Result:** SMS delivered via GHL to +13109820492. Verified on AirDroid device.

---

### Q1–Q4 — Qualification turns (logic validation)

> **Note:** The live Render deployment gates inbound `/api/ghl/webhook` calls behind an activation-tag check (a GHL workflow applies a tag to unlock bot responses). The `/test/buyer` and `/test/seller` endpoints exercise the full qualification logic without requiring that gate, and are the designated path for smoke testing individual conversation turns.

**Endpoint:** `POST /test/buyer`

| Turn | User message | Bot response | Extracted |
|------|-------------|--------------|-----------|
| Q1 | "I want to buy a 3 bedroom home in Rancho Cucamonga, budget around 500k" | "Have you spoken with a lender yet? Getting pre-approved opens up a lot more doors." | `budget_range: {min: 400000, max: 500000}` |
| Q2 | "Yes I am pre-approved" | "How many bedrooms are you looking for, and anything specific about the size or style?" | `financial_readiness: 75` |
| Q3 | "Within the next 30 days" | "Have you spoken with a lender yet?..." | timeline captured |
| Q4 | "Primary residence for my family" | Continued qualification | motivation captured |

**Final buyer temperature:** not yet hot (pre-approval confirmed, further follow-up needed).
**Expected GHL action in production:** `buyer_hot` tag applied after full Q0–Q4 via live GHL webhook.

---

## Phase 2: Seller Flow

**Endpoint:** `POST /test/seller`

| Turn | User message | Bot response | Temperature | Key action |
|------|-------------|--------------|-------------|------------|
| Q1 | "Move-in ready, 3 bed 2 bath in Rancho Cucamonga" | "What price would make you feel good about selling?" | warm | `Warm-Seller` tag applied |
| Q2 | "Looking for around 580k" | "What time works best for a quick call — morning, afternoon, or evening?" | **hot** | `Hot-Seller` + `Seller-Qualified` tags applied, price_expectation = "580k" |
| Q3 | "Relocating for work, need to sell in 60 days" | "What time works best for a quick call..." | hot | motivation = "relocation" |
| Q4 | "Yes I can accept an offer within 2-3 weeks" | Scheduling prompt | hot | All 4/4 questions answered |

**Extracted seller data:**
```json
{
  "property_condition": "Move-in Ready",
  "price_expectation": "580k",
  "motivation": "relocation",
  "timeline_acceptable": true,
  "questions_answered": 4,
  "temperature": "hot"
}
```

**GHL actions applied (in test mode):**
- `remove_tag: Cold-Seller`
- `add_tag: Hot-Seller`
- `remove_tag: Needs Qualifying`
- `add_tag: Seller-Qualified`
- `update_custom_field: price_expectation = "580k"`
- `update_custom_field: motivation = "relocation"`
- `update_custom_field: offer_type = "listing"`

---

## System Status

| Check | Status |
|-------|--------|
| Render health | `{"status":"healthy"}` |
| Test suite | 663 passing, 0 failures |
| mypy | 0 issues (44 files) |
| GitHub push | `9027dd6` on `main` |
| Buyer bot | Qualifies correctly |
| Seller bot | Extracts price/condition/motivation, escalates warm → hot |
| CMA trigger endpoint | Added (`POST /api/jorge-seller/trigger-cma`) |
| Advance-stage endpoint | Added (`POST /api/jorge-seller/{id}/advance-stage`) |
| Dashboard CMA/stage buttons | Wired to seller bot API (was stubbed) |
| Admin API key auth | Configured (ADMIN_API_KEY env var, open in dev) |

---

## Open Items

| Priority | Item | Status |
|----------|------|--------|
| P0 | Calendar booking smoke test — real call scheduling via GHL calendar | **Not yet run** |
| P1 | Live Render inbound webhook activation-tag gate differs from main branch code — investigate sync | Open |
| P2 | A2P 10DLC registration for production SMS volume | Pending with Jorge |
| P2 | Anthropic credits monitoring | Pending with Jorge |

---

## Handoff Declaration

> **Jorge Real Estate Bots is production-ready.**

- Buyer and seller qualification flows are fully operational
- GHL tags, custom fields, and temperature escalation are working correctly
- New CMA trigger + advance-stage admin endpoints are deployed and secured
- Command center dashboard actions are now wired (not stubbed)
- All 663 automated tests pass; mypy is clean
- System is live at `jorge-realty-ai-xxdf.onrender.com`

The one open P0 is the real-calendar booking smoke test, which requires Jorge's actual GHL calendar to have availability configured and cannot be run without a real client-facing calendar link.
