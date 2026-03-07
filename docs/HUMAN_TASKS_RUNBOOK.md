# Human Tasks Runbook

> **Audience**: Cayman Roden (Render/ops) and Jorge Salas (GHL).
> **Purpose**: Exact steps to complete the 4 remaining human-action blockers before production handoff is marked `ready`.
> **When complete**: Update `docs/JORGE_PRODUCTION_HANDOFF_SIGNOFF.md` rows and flip STATUS to `ready`.

---

## Cayman — Task 1: DB Plan Upgrade

**Why**: Free-tier `jorge-realty-db` expires 2026-03-24. Data loss risk if not upgraded.
**Time**: ~5 minutes.

### Steps

1. Open [Render Dashboard](https://dashboard.render.com) → **Databases**.
2. Click **`jorge-realty-db`**.
3. Click **Change Plan** (top-right).
4. Select **Starter ($7/month)** → **Confirm**.
5. Wait for plan change to complete (~1–2 min, no downtime).

### Verification

```bash
curl https://jorge-realty-ai-xxdf.onrender.com/health/aggregate
```

Expected response:
```json
{"postgres": "ok", "redis": "ok", "status": "healthy"}
```

Also use the new schema-check endpoint:
```bash
curl https://jorge-realty-ai-xxdf.onrender.com/health/schema-check
```

Expected response includes `"postgres": "ok"` and 9 Jorge tables listed.

### Signoff

Update `docs/JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`:
- Row `jorge-realty-db upgraded` → **Pass** with date.

---

## Cayman — Task 2: First Live SMS

**Why**: Validates end-to-end webhook flow, populates first DB record, unblocks contact-specific endpoint checks.
**Time**: ~10 minutes (5 min bot reply window).

### Prerequisites

- DB plan upgraded (Task 1 above).
- Bot is deployed on Render (check `https://jorge-realty-ai-xxdf.onrender.com/health`).

### Steps

1. From test phone **`(310) 982-0492`**, text the Jorge GHL number **`+1 (909) 255-3781`**:
   ```
   Hi, I'm interested in selling my home at 123 Main St
   ```
2. Wait up to **5 minutes** for bot reply.

### Verification

After receiving bot reply:

```bash
# Get the contact_id from GHL for phone (310) 982-0492, then:
curl -H "Authorization: Bearer REDACTED_ADMIN_KEY" \
  https://jorge-realty-ai-xxdf.onrender.com/admin/conversations/<contact_id>
```

Expected: HTTP 200 with conversation record (not 404).

Also confirm in GHL → Contacts → find `(310) 982-0492` → check `Bot Type` field is set to `seller`.

### Signoff

Update `docs/JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`:
- Row `GET /admin/conversations/{contact_id}` → **Pass**.
- Row `Suppression/handoff reasons visible` — verify or note pending.

---

## Cayman — Task 3: Manual Takeover Test

**Why**: Validates the `Jorge-Active` tag suppression path end-to-end on live GHL.
**Time**: ~10 minutes.

### Prerequisites

- Task 2 complete (live contact in DB).
- You have access to GHL Contacts UI.

### Steps

**Part A — Enable takeover:**

1. In GHL → **Contacts** → find the test contact (phone `310-982-0492`).
2. Click **Add Tag** → type `Jorge-Active` → Save.
3. From test phone, send another SMS:
   ```
   Are you still there?
   ```
4. Wait 3 minutes. **Expected: no bot reply** (takeover suppression active).

**Part B — Resume:**

5. In GHL → Contacts → find same contact.
6. Remove the `Jorge-Active` tag.
7. From test phone, send:
   ```
   What's the next step?
   ```
8. Wait up to 5 minutes. **Expected: bot replies** (suppression lifted).

### Verification

After Part A: confirm no bot reply received within 3 min.
After Part B: confirm bot reply received within 5 min.

Optionally check suppression log:
```bash
curl -H "Authorization: Bearer REDACTED_ADMIN_KEY" \
  https://jorge-realty-ai-xxdf.onrender.com/admin/conversations/<contact_id>
```

Look for `suppression_reason` or `handoff` fields in response.

### Signoff

Update `docs/JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`:
- Row `Manual takeover` → **Pass**.
- Row `Resume after takeover` → **Pass**.

---

## Jorge — Task 4: GHL Workflow Audit

**Why**: Two specific workflows may conflict with bot routing. Must be confirmed before full go-live.
**Time**: ~30–60 minutes (depends on GHL UI speed).

### How To Use the Checklist

Open `docs/GHL_WORKFLOW_AUDIT_CHECKLIST.md`. It lists 16 workflows in priority order.

For each workflow:
1. Click the GHL workflow URL.
2. Check the **Trigger** tab — what event fires this workflow?
3. Check the **Actions** tab — does any action write the `Bot Type` custom field?
4. Answer the checklist questions in the doc.

### Critical Workflows (Must Check First)

#### Workflow `d43d02f5` — "2. AI OFF/ON Tag Added"

- Open in GHL: search workflow list for `2. AI OFF/ON Tag Added`.
- **Check Actions tab**: Does any action write to the `Bot Type` custom field?
- **Must NOT** write `Bot Type` with any value. If it does, **disable that action** immediately.
- Note: this workflow adding/removing the `ai off` or `ai-off` tag is fine — those tags only affect GHL native AI, not the Jorge app.

#### Workflow `11c4943e` — "5. Process Message - Which Bot?"

- Open in GHL: search for `5. Process Message - Which Bot?`.
- **Check Actions tab**: Does the webhook action point exclusively to `https://jorge-realty-ai-xxdf.onrender.com/webhook/lead`?
- Must relay **only** to the Jorge app webhook. No other destination allowed.
- If webhook URL is wrong, update it to the correct URL above.

### For All Other Tier 1 Workflows

See `docs/GHL_WORKFLOW_AUDIT_CHECKLIST.md` for the full list of 8 Tier 1 workflows.

### Signoff

Once all Tier 1 workflows confirmed:

Update `docs/JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`:
- Row `Workflow inventory completed` → **Pass**.
- Row `Conflicting workflows removed/disabled` → **Pass** (or note any disabled workflows).
- Row `Legacy fields not driving routing` → **Pass** (once `Bot Type` write is confirmed absent from workflows).

---

## Jorge — Task 5: Calendar Write Scope

**Why**: GHL returns HTTP 404 on `POST /calendars/events`. Likely missing `Calendars (Write)` scope on the private integration. Fixing this enables automatic booking.
**Time**: ~5 minutes.

### Steps

1. In GHL → **Settings** → **Integrations** → **Private Integrations**.
2. Find the integration used by the Jorge app (look for the API key matching `GHL_API_KEY` in Render env vars).
3. Click **Edit** (or **Manage Scopes**).
4. Check that **Calendars (Write)** is enabled.
5. If not, enable it and click **Save**.

### Verification

```bash
# Test a booking attempt via the webhook (seller lead flow triggers booking on hot/qualified)
# Or check logs after next real qualified lead
```

The bot currently falls back to a prose message + human handoff when booking fails — this is safe. But fixing the scope enables automatic calendar booking.

### Signoff

Update `docs/JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`:
- Row `Scheduling or fallback` → **Pass** (full, not partial).

---

## Final: Mark Handoff Ready

Once all 5 tasks above are complete, update the signoff doc:

1. Set `Handoff decision: ready` (line 14).
2. Fill in approval lines:
   ```
   - App/runtime owner: ✅ Cayman Roden — [DATE]
   - GHL workflow owner: ✅ Jorge Salas — [DATE]
   - Operator / Jorge: ✅ Jorge Salas — [DATE]
   - Final signoff date: [DATE]
   ```
3. Commit: `docs: mark production handoff ready — all blockers cleared`

---

## Quick Reference

| Item | Value |
|------|-------|
| Production URL | `https://jorge-realty-ai-xxdf.onrender.com` |
| GHL number | `+1 (909) 255-3781` |
| Test phone | `(310) 982-0492` |
| Admin API key | `REDACTED_ADMIN_KEY` |
| Admin header | `Authorization: Bearer <key>` or `X-Admin-Key: <key>` |
| DB upgrade deadline | 2026-03-24 (free tier expires) |
| Render dashboard | `https://dashboard.render.com` |
| DB plan target | Starter ($7/mo) |
