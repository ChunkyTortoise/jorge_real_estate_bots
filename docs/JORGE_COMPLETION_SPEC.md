# Jorge Real Estate Bots — Completion Spec

> **Purpose**: Single source of truth for what remains before handoff can be marked `ready`.
> **Status as of 2026-03-07**: Production is live, postgres healthy, 7/9 live scenarios passing.
> Two blocking items remain before signoff: GHL workflow audit and DB tier upgrade.

---

## Current State

| Area | Status |
|---|---|
| Deployment | Live — `sha-b9d4d8c` at `jorge-realty-ai-xxdf.onrender.com` |
| Environment | `production` confirmed |
| Postgres | Healthy — 9 Jorge tables exist |
| Redis | Healthy |
| Dashboard endpoints | All passing |
| Seller scenario (API) | Pass |
| Buyer scenario (API) | Pass |
| Ambiguous scenario (API) | Pass |
| Bilingual handoff (API) | Pass |
| Duplicate/race safety | Pass |
| Qualified outcome | Pass |
| Scheduling fallback | Pass (booking itself is a known 404 bug) |
| Manual takeover | **Blocked** — needs live GHL tag test |
| Resume after takeover | **Blocked** — depends on manual takeover |
| GHL workflow audit | **Blocked** — 8 Tier 1 workflows unconfirmed in GHL UI |
| DB tier | **At risk** — free tier expires 2026-03-24 |

---

## Blocking Items (must complete before handoff `ready`)

### B1 — GHL Workflow UI Audit
**Owner**: Jorge Salas (GHL admin access required)
**Deadline**: Before any live SMS traffic is enabled

The live GHL location has 226 workflows, 68 flagged as potential routing conflicts.
16 have been pre-classified by name. 8 Tier 1 workflows need GHL UI confirmation of
their exact trigger and action list before live messaging is safe.

**Required actions** (log results in `docs/JORGE_GHL_WORKFLOW_INVENTORY.md`):

| Priority | Workflow | Key Question | Required Outcome |
|---|---|---|---|
| **P1** | `5. Process Message - Which Bot?` | Does it call the app webhook (`POST /api/ghl/webhook`) or route independently? | Keep if relay to app. Rewrite/disable if it routes without calling app. |
| **P1** | `2. AI OFF/ON Tag Added -> AI Assistant is:` | Does it write the `Bot Type` custom field? | Must NOT write `Bot Type`. If it does, remove that action. |
| **P1** | `Jorge AI Bot - Inbound Message Handler` | Does it send AI-generated messages via GHL native AI (not via the app)? | Must be HTTP relay to app only. If it sends direct AI messages, disable it — the app handles replies. |
| **P1** | `6. Catch Unknown Inbound SMS` | Does it fire on contacts the app is managing? | Must exclude Jorge-handled contacts (e.g. filter by Jorge-Active tag presence/absence). |
| **P1** | `New Inbound Lead` | Does it send messages before the app processes the webhook? | Must either be the app relay, or send only after app has been called. |
| **P2** | `Jorge — Bot Activation` | What tags/fields does it write on activation? | Must not write `Bot Type`, `agent bot`, `buyer bot`, or `direct to *` tags. |
| **P2** | `AI Bot - Jorge Qualification` | Does it independently qualify leads or relay to the app? | Must relay to app. |
| **P2** | `Qualified Lead Notify - SMS` | Does it SMS the contact or only the operator? | If it SMSes the contact, it conflicts with the app's own qualification response. Disable or restrict recipient to operator. |

**Acceptance criteria**: Every Tier 1 row in `JORGE_GHL_WORKFLOW_INVENTORY.md` has
`GHL UI Confirmed? = Yes` with trigger + action details filled in, and an explicit
`keep` / `rewrite` / `disable` disposition.

---

### B2 — DB Tier Upgrade
**Owner**: Cayman Roden (Render dashboard)
**Deadline**: Before 2026-03-24 (free tier expiry)

The `jorge-realty-db` Render Postgres instance is on the free tier, which expires
and deletes all data on 2026-03-24. The app is now writing to this DB (conversations,
leads, etc.). Data loss will occur if not upgraded.

**Steps**:
1. Go to Render dashboard → `jorge-realty-db` → Upgrade plan
2. Choose Starter or Standard tier ($7/mo or $20/mo)
3. Confirm `DATABASE_URL` is unchanged after upgrade (internal URL format stays the same)
4. Verify `/health/aggregate` still shows `postgres = ok` after upgrade

**Acceptance criteria**: `jorge-realty-db` is on a paid tier. Expiry date removed.

---

### B3 — Manual Takeover + Resume Live Test
**Owner**: Cayman Roden (can be done via API or SMS)
**Prerequisite**: At least one contact must have been processed by the bot (i.e., a real or test inbound message sent to the Jorge GHL number and processed by the app webhook)

**Steps**:

1. Send a test inbound SMS to the Jorge number (or POST to `/api/ghl/webhook` with a real `contactId`)
2. Confirm the contact now has a DB record: `GET /admin/conversations/{contact_id}` returns 200
3. **Manual takeover test**:
   - Add `Jorge-Active` tag to the test contact in GHL
   - Send another inbound message
   - Confirm the app does NOT reply (suppressed)
   - Confirm `GET /admin/conversations/{contact_id}` shows `status = suppressed`
4. **Resume test**:
   - Remove `Jorge-Active` tag from the contact in GHL
   - Send another inbound message
   - Confirm the app resumes replying correctly
   - Confirm conversation does not restart from scratch

**Acceptance criteria**: Both scenarios pass. Update `JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`
with `Pass` for manual takeover and resume rows.

---

## Non-Blocking Items (complete after signoff or in parallel)

### N1 — First Live Contact Processing
**Owner**: Cayman Roden
**Why**: Unlocks contact-specific endpoint validation and live scenario checklist completion

Send a real or test inbound SMS to the Jorge GHL number. This creates the first DB record
and unblocks:
- `GET /admin/conversations/{contact_id}` (currently returns 404 — no DB records yet)
- `GET /api/dashboard/leads/{contact_id}`
- `GET /api/dashboard/conversations/{contact_id}`
- Suppression/handoff reason visibility

---

### N2 — GitHub Secret: DATABASE_URL
**Owner**: Cayman Roden
**Why**: Prevents future deploy regressions if the env var PUT step is ever re-added

1. Go to GitHub → `ChunkyTortoise/jorge_real_estate_bots` → Settings → Secrets → Actions
2. Add secret: `DATABASE_URL` = `postgresql://jorge_realty:REDACTED_POSTGRES_PASSWORD@dpg-d6d54hn5r7bs73aq6rkg-a/jorge_realty`
3. (Optional) Restore the env var reset step in `deploy.yml` once all 15 secrets are set

---

### N3 — GHL Calendars.Write Scope (Booking 404)
**Owner**: Jorge Salas (GHL admin) + Cayman Roden (API key scope)
**Why**: `POST /calendars/events` returns 404. Scheduling fallback is in place, so this
is not blocking. But full booking capability requires this fix.

**Investigation steps**:
1. In GHL → Settings → Integrations → API: check the API key's scopes
2. Confirm `calendars.write` is enabled; if not, regenerate the key with that scope
3. Update `GHL_API_KEY` in Render env vars
4. Test booking via `GET /admin/calendar-debug` (if available) or direct API call

---

### N4 — Warm Nurture Workflow Safety Check (Tier 2)
**Owner**: Jorge Salas
**Why**: `Jorge — Warm Buyer Nurture` and `Jorge — Warm Seller Nurture` have routing logic.
If they send SMS to contacts, they can conflict with app-managed conversations.

Confirm in GHL UI:
- These workflows send notifications to Jorge (the operator), not to contacts
- OR they only fire for contacts not currently managed by the app (no Jorge-Active in progress)

---

### N5 — Compatibility Shim Disposition
**Owner**: Cayman Roden
**Prerequisite**: Live scenario validation complete

Review `docs/COMPATIBILITY_SHIMS.md`. Once live traffic confirms no legacy callers
depend on the shims, remove:
- `assigned_bot:{contact_id}` Redis key writes
- `bot_type` request field compatibility in webhook handler
- Metadata fallback in canonical extractor

Each shim has a removal trigger documented in `COMPATIBILITY_SHIMS.md` and the handoff signoff.

---

### N6 — Bot Type Field Live Check
**Owner**: Cayman Roden (API call)
**Why**: App reads `Bot Type` (key `bot_type`) custom field for routing. If any contact
has this set to a non-empty value by a legacy GHL workflow, it overrides canonical mode detection.

```bash
# Check a known test contact
curl -s "https://services.leadconnectorhq.com/contacts/{contact_id}" \
  -H "Authorization: Bearer $GHL_API_KEY" \
  -H "Version: 2021-07-28" | jq '.contact.customFields[] | select(.key == "bot_type")'
```

If any contact has `bot_type` set by GHL (not by the app), identify which workflow
writes it and confirm it's safe (see B1, item P1: `2. AI OFF/ON Tag Added`).

---

## Acceptance Gate — Handoff Ready

Mark `JORGE_PRODUCTION_HANDOFF_SIGNOFF.md` status as `ready` when ALL of the following are true:

- [x] Environment = production
- [x] Postgres healthy, 9 tables exist
- [x] Redis healthy
- [x] All dashboard endpoints returning 200
- [x] Seller, buyer, ambiguous, bilingual scenarios pass (API-level)
- [x] Duplicate/race safety passes
- [ ] **B1**: GHL Tier 1 workflow audit complete (all 8 workflows confirmed in GHL UI)
- [ ] **B2**: `jorge-realty-db` upgraded to paid tier
- [ ] **B3**: Manual takeover + resume live test passes

---

## Remaining Test Execution

After B1–B3 are complete, run the full live checklist in `docs/JORGE_LIVE_VALIDATION_CHECKLIST.md`.
Scenarios 5 (manual takeover), 6 (resume), and 10 (human handoff) are the only
unchecked ones. All others have been API-validated.

---

## Rollback Reference

- Last stable image: `sha-b9d4d8c` (deployed 2026-03-06, dep-d6lq8ntactks73fm2fd0)
- Rollback via: Render dashboard → jorge-realty-ai → Deploys → redeploy previous
- Internal postgres URL: `postgresql://jorge_realty:REDACTED_POSTGRES_PASSWORD@dpg-d6d54hn5r7bs73aq6rkg-a/jorge_realty`
- Admin key: `REDACTED_ADMIN_KEY` (header `X-Admin-Key`)
