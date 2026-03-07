# Jorge GHL Bots — Remaining Handoff Spec

**As of**: 2026-03-07
**Status**: 1717 tests passing, commit `55fdea4`. **2 human-action blockers (B1, B4) remain — both require Jorge Salas (GHL owner).** B2 + B3 + N4 + N5 + N6 all DONE.
**Full detail**: `memory/jorge-project.md`, `docs/JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`

---

## A. Code Tasks — ALL DONE

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| N4 | Compatibility shim assessment | ✅ DONE | 3 shims documented in `docs/COMPATIBILITY_SHIMS.md`. All safe to keep — removal blocked on 2 weeks stable live traffic. |
| N5 | Startup env validation | ✅ DONE | Lifespan validates 5 env vars (`ANTHROPIC_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `GHL_API_KEY`, `GHL_LOCATION_ID`). Added as part of T6. |
| N6 | Hardcoded test credentials | ✅ DONE | Searched `bots/lead_bot/main.py` ~line 488 — zero hardcoded credentials or test contact IDs found in production paths. |

---

## B. Human Actions (require browser/account access)

| ID | Who | What | Urgency |
|----|-----|------|---------|
| B1 | Jorge Salas (GHL owner) | Workflow UI audit — 8 Tier 1 workflows | High — must confirm no conflicts before traffic scales |
| ~~B2~~ | ~~Cayman Roden~~ | ~~DB tier upgrade~~ | ✅ **DONE (2026-03-07)** — upgraded `free` → `basic_256mb` via Render API. No expiry. |
| B4 | Jorge Salas (GHL owner) | Enable Calendars.Write API scope | Medium — booking returns 404 until done |
| N3 | Jorge Salas (GHL owner) | Warm nurture workflow recipient safety check | Low — prevent accidental mass SMS |

### B1 — GHL Workflow UI Audit

**Who**: Jorge Salas (GHL owner login required — sub-user cannot access Automation page)
**How**: Open `docs/GHL_WORKFLOW_AUDIT_CHECKLIST.md` — 16-item checklist covering all 8 Tier 1 workflows
**What to confirm**: Each workflow's trigger conditions and actions don't double-fire or conflict with bot routing
**Known workflows** (confirmed via API, IDs for reference):
- "New Inbound Lead" `da046656-...`
- "5. Process Message - Which Bot?" `11c4943e-...`
- "Jorge — Hot Seller Notification" `577d56c4-...`
- "Jorge — Hot Buyer Notification"
- "Jorge — Agent Notification" `f3fc268b-...`
- "Jorge — Manual Scheduling Fallback" `9610d6fe-...`
- "Jorge — Warm Buyer Nurture" `fbcef074-...` (PUBLISHED)
- "Jorge — Warm Seller Nurture" `c8334775-...` (PUBLISHED)

### ~~B2~~ — Render DB Tier Upgrade — ✅ DONE

`jorge-realty-db` upgraded `free` → `basic_256mb` via Render API (2026-03-07). No expiry date. `postgres=ok` confirmed via `/health/aggregate`. No further action needed.

### B4 — Enable Calendars.Write API Scope

**Who**: Jorge Salas (GHL owner login required — Private Integrations page blocked for sub-users)
**Steps**:
1. Log in to GHL as account owner
2. Settings → Private Integrations
3. Find the Jorge API key (`(see Render dashboard)`)
4. Edit → Scopes → Calendars → enable **Write**
5. Save
6. Run verification curl below — booking should return 200 instead of 404

### N3 — Warm Nurture Workflow Safety Check

**Who**: Jorge Salas
**What**: Open "Jorge — Warm Buyer Nurture" and "Jorge — Warm Seller Nurture" in GHL Automation
**Confirm**: The email/SMS recipients are set to **Jorge only** (not the contact/lead list). These workflows should notify Jorge, not blast his contacts.

---

## C. Verification Steps

Run after all items complete:

```bash
# 1. Full test suite — must stay green
cd ~/Projects/jorge-real-estate-bots
pytest tests/ -q

# 2. Health aggregate
curl -H "X-Admin-Key: (see Render dashboard)" \
  https://jorge-realty-ai-xxdf.onrender.com/health/aggregate
# Expected: {"postgres": "ok", "redis": "ok"}

# 3. Suppression test — after any redeploy, confirm B3 fix is live
# Add 'jorge-active' tag to test contact in GHL, then send webhook:
curl -X POST https://jorge-realty-ai-xxdf.onrender.com/api/ghl/webhook \
  -H "Content-Type: application/json" \
  -d '{"type":"InboundMessage","contactId":"Eh9V2pQ1VpJYzd7xiVYC","body":"test"}'
# Expected: {"status":"suppressed"} (bot should NOT reply when jorge-active tag is set)

# 4. Calendar booking test — after B4 (Calendars.Write scope enabled)
curl -X POST \
  -H "X-Admin-Key: (see Render dashboard)" \
  -H "Content-Type: application/json" \
  -d '{"contact_id":"Eh9V2pQ1VpJYzd7xiVYC","slot_index":0}' \
  https://jorge-realty-ai-xxdf.onrender.com/api/admin/calendar-debug
# Expected: 200 (was 404 before B4)

# 5. DB schema check (after B2 — confirms DB still accessible post-upgrade)
curl -H "X-Admin-Key: (see Render dashboard)" \
  https://jorge-realty-ai-xxdf.onrender.com/health/schema-check
# Expected: {"tables": ["contacts","conversations","leads","deals","commissions","properties","buyer_preferences","playbook_applications","roi_reports"]}
```

---

## D. Definition of Done

All of the following must be true:

- [ ] B1: GHL workflow audit complete, no conflicts found (or conflicts fixed)
- [x] ~~B2: DB upgraded before 2026-03-24~~ — **DONE (2026-03-07)** `basic_256mb`, no expiry
- [ ] B4: Calendars.Write scope enabled, booking returns 200
- [ ] N3: Warm nurture workflows verified — recipients = Jorge only
- [x] N4: Shim assessment documented in `docs/COMPATIBILITY_SHIMS.md` — 3 shims, all safe to keep
- [x] N5: Startup env validation confirmed present (5 vars, lifespan block)
- [x] N6: Hardcoded test credentials — zero found in production paths
- [x] `pytest tests/ -q` — 1717 passing (2026-03-07, commit `55fdea4`)
- [x] `/health/aggregate` returns `{"postgres":"ok","redis":"ok"}`
- [x] Suppression test returns `suppressed` for `jorge-active` contacts (B3 DONE)
- [ ] Signoff doc `docs/JORGE_PRODUCTION_HANDOFF_SIGNOFF.md` STATUS updated to `ready`

---

## E. Key Credentials Reference

| What | Value |
|------|-------|
| Live URL | `https://jorge-realty-ai-xxdf.onrender.com` |
| Admin API Key | `(see Render dashboard)` |
| Render service ID | `srv-d6d5go15pdvs73fcjjq0` |
| GHL API Key | `(see Render dashboard)` |
| GHL Location ID | `3xt4qayAh35BlDLaUv7P` |
| Redis URL | `redis://red-d6d54jfpm1nc739jgnm0:6379` |
| Test contact (seller) | `Eh9V2pQ1VpJYzd7xiVYC` |
| Test contact (buyer) | `j4BMPgScf0C1788mnUl8` |
| First live contact | `prX3fC1c7UaCjUzwdeyu` (N1, 2026-03-07) |

**All secrets** in Render env vars (18 total). See `docs/HUMAN_TASKS_RUNBOOK.md` for full runbook.
