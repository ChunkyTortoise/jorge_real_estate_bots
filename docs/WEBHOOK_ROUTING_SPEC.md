# Jorge Bots — Webhook Routing & Bot-Activation Spec

## Context

This spec defines four targeted fixes needed before full production use:

| # | Issue | Severity |
|---|-------|----------|
| 1 | GHL webhook not routing to the correct bot | P0 |
| 2 | Wrong bot's message sent for contact type | P0 |
| 3 | All three bots can fire simultaneously for one contact | P1 |
| 4 | Tags added immediately — need 30-second delay | P1 |

---

## Current Architecture (Confirmed by Code Audit)

```
GHL → POST /api/ghl/webhook
        │
        ├─ Signature verification (RSA / HMAC)
        ├─ Deduplication (5-min TTL)
        ├─ Per-contact Redis lock: lock:{contact_id} (30s TTL, wait up to 10s)
        │
        ├─ bot_type resolution (routes_webhook.py:161–183):
        │     1. payload.customData.bot_type
        │     2. payload.customData."Bot Type"
        │     3. payload.bot_type
        │     4. GHL contact API → customFields[].fieldKey == "bot_type"
        │     5. Default: "lead"
        │
        ├─ ROUTING (mutually exclusive if/elif/else — one bot only per call):
        │     "seller" in bot_type → seller_bot.process_seller_message()
        │     "buyer"  in bot_type → buyer_bot.process_buyer_message()
        │     else                 → lead_analyzer.analyze_lead()  [no SMS]
        │
        ├─ Inside process_seller/buyer_message():
        │     1. Load Redis state
        │     2. Generate Claude response
        │     3. _apply_ghl_actions() — tags + custom fields  ← TAGS FIRE HERE
        │            asyncio.wait_for(..., timeout=10s)       ← hard cap
        │     4. Return SellerResult / BuyerResult
        │
        └─ Webhook sends SMS AFTER bot returns            ← tags already fired

Tags applied BEFORE SMS is delivered to the contact.
GHL tag-triggered workflows can start before contact reads the reply.
```

### Actual problems (confirmed)

| # | Problem | Root cause |
|---|---------|-----------|
| ① | Wrong bot handles the contact | `bot_type` field not set in GHL before inbound SMS hits webhook |
| ② | Buyer contact gets seller questions (or vice versa) | Same as ① — blank `bot_type` defaults to lead analysis (no SMS) OR wrong workflow sends wrong `bot_type` |
| ③ | Multiple bots can process the same contact across different webhook calls | No Redis key recording which bot owns the contact; lock only prevents *concurrent* calls |
| ④ | Tags fire immediately, before SMS is delivered | `_apply_ghl_actions()` runs inside the bot, before `send_message()` is called in the webhook |

---

## Fix 1 — GHL Webhook Configuration

### Root Cause

The webhook payload must include `bot_type` so the dispatcher can route correctly.
If GHL sends the message without this field (or with the wrong value), the
dispatcher defaults to **lead analysis** and sends **no SMS reply**.

The buyer/seller bots produce the correct message content — the only issue is
whether the payload tells the router which one to invoke.

### Required GHL Configuration

#### Step 1 — Create a "Bot Type" custom field

In GHL → Settings → Custom Fields → Contacts:
```
Field Name:  Bot Type
Field Key:   bot_type         ← must match exactly (snake_case)
Field Type:  Text / Dropdown
Options:     lead, seller, buyer
```

#### Step 2 — Set bot_type when a contact is created or assigned

**New Seller Lead Workflow:**
1. Trigger: Contact created OR tag "seller-intent" added
2. Action: Update Custom Field → `Bot Type = seller`
3. Action: Send Webhook (see Step 3)

**New Buyer Lead Workflow:**
1. Trigger: Contact created OR tag "buyer-intent" added
2. Action: Update Custom Field → `Bot Type = buyer`
3. Action: Send Webhook (see Step 3)

#### Step 3 — Webhook Action Payload

Every GHL workflow that sends to the Jorge webhook must include `bot_type`
in the **Custom Data** section of the Send Webhook action:

```json
{
  "contactId": "{{contact.id}}",
  "locationId": "{{location.id}}",
  "body": "{{message.body}}",
  "fullName": "{{contact.fullName}}",
  "phone": "{{contact.phone}}",
  "email": "{{contact.email}}",
  "customData": {
    "bot_type": "{{contact.bot_type}}"
  }
}
```

> **Important:** `{{contact.bot_type}}` must reference the custom field created
> in Step 1. If GHL uses `{{custom_fields.bot_type}}` instead, adjust accordingly
> for your GHL plan/version.

#### Step 4 — Inbound SMS Trigger

Create one GHL workflow per bot type:

| Workflow | Trigger | Filter | Action |
|----------|---------|--------|--------|
| `Seller Bot Relay` | Inbound SMS received | Contact field `Bot Type = seller` | Send Webhook to `POST /api/ghl/webhook` |
| `Buyer Bot Relay` | Inbound SMS received | Contact field `Bot Type = buyer` | Send Webhook to `POST /api/ghl/webhook` |
| `Lead Bot Relay` | Inbound SMS received | Contact field `Bot Type = lead` OR is empty | Send Webhook to `POST /api/ghl/webhook` |

Each workflow passes the payload from Step 3.

---

## Fix 2 — Bot-Message Pairing (Buyer Message = Buyer Bot)

### Root Cause

The dispatcher (`routes_webhook.py` lines 201-237) already correctly routes:
- `bot_type=seller` → `seller_bot.process_seller_message()` → seller SMS
- `bot_type=buyer`  → `buyer_bot.process_buyer_message()` → buyer SMS

**There is no code bug here.** The issue is purely configuration:
if a buyer contact's GHL workflow sends `bot_type=seller` (or blank), the
seller bot fires and sends seller-qualification questions to a buyer.

Fix 1 (above) resolves this completely. After Fix 1 is applied, a buyer
contact will always have `Bot Type = buyer` before their inbound messages
reach the webhook.

### Verification

After deploying Fix 1, test with a fresh buyer contact:
1. Set `Bot Type = buyer` on the contact in GHL
2. Text "hi I want to buy a home"
3. The webhook log should show: `bot_type='buyer'`
4. The SMS reply should ask about **bedrooms, budget, area** (buyer Q1)
5. It must NOT ask "what condition is the house in?" (seller Q1)

---

## Fix 3 — Only One Bot Active at a Time

### What the existing lock DOES (confirmed)

The `lock:{contact_id}` Redis key (TTL 30s) prevents **concurrent** webhook
calls for the same contact from racing. If call A is processing contact X, call
B for the same contact waits up to 10 seconds, then returns `throttled` if the
lock is still held. This is correct and working.

### What the lock does NOT do

The lock has **no memory across calls**. Once call A finishes and releases the
lock, call B (which arrived one second later) can process the same contact with
a completely different `bot_type`. There is no record of "contact X is a buyer
contact — ignore seller-routed calls."

### Root Cause

Example failure mode:
1. GHL accidentally fires both a Seller Relay workflow and a Buyer Relay workflow
   for the same contact (e.g., contact has both seller-intent and buyer-intent tags)
2. Call A arrives with `bot_type=seller` → seller bot runs, sends seller Q1 SMS
3. Call B arrives 5 seconds later with `bot_type=buyer` → lock already released →
   buyer bot runs, sends buyer Q1 SMS
4. Contact receives two contradictory first messages

### Required Code Change — `routes_webhook.py`

Add a **bot-assignment lock** keyed by `contact_id`. Once a bot type is
confirmed active for a contact, any webhook with a *different* bot type for
that same contact is rejected.

#### `routes_webhook.py` — after line 184 (bot_type determined), add:

```python
# --- Bot-assignment exclusivity check ---
# Once a contact is assigned to a bot, reject messages from other bots.
if _webhook_cache:
    assigned_key = f"assigned_bot:{contact_id}"
    assigned_bot = await _webhook_cache.get(assigned_key)

    if assigned_bot and assigned_bot != bot_type_lower:
        logger.info(
            f"Contact {contact_id} assigned to '{assigned_bot}', "
            f"rejecting '{bot_type_lower}' bot request"
        )
        return {"status": "skipped", "reason": "bot_assignment_conflict"}

    if not assigned_bot:
        # First contact with this bot — record assignment (7-day TTL matches state TTL)
        await _webhook_cache.set(assigned_key, bot_type_lower, ttl=604800)
```

#### How to Clear the Assignment

When Jorge manually reassigns a contact to a different bot type:
1. Update `Bot Type` field in GHL
2. The next GHL workflow trigger sends the new `bot_type`
3. The old `assigned_bot:{contact_id}` key must be cleared

Add an admin endpoint:
```python
# routes_admin.py
@router.post("/admin/reassign-bot")
async def reassign_bot(contact_id: str, new_bot_type: str):
    """Clear the bot assignment cache for a contact so the new bot_type takes effect."""
    cache = get_cache_service()
    await cache.delete(f"assigned_bot:{contact_id}")
    await cache.set(f"assigned_bot:{contact_id}", new_bot_type.lower(), ttl=604800)
    return {"status": "ok", "contact_id": contact_id, "bot_type": new_bot_type}
```

Or, more simply: when `bot_type` arrives and differs from the stored assignment,
**overwrite it** if it comes with an explicit payload value (not a GHL API
fallback). The heuristic: if `bot_type` was found in the payload directly
(not from the contact API lookup), trust it as an intentional reassignment.

```python
# After bot_type determination (line 184), differentiate payload vs API source:
bot_type_from_payload = bool(
    custom_data.get("bot_type")
    or custom_data.get("Bot Type")
    or payload.get("bot_type")
)

assigned_key = f"assigned_bot:{contact_id}"
if _webhook_cache:
    assigned_bot = await _webhook_cache.get(assigned_key)
    if assigned_bot:
        if assigned_bot != bot_type_lower:
            if bot_type_from_payload:
                # Explicit override — reassign
                logger.info(f"Reassigning {contact_id}: {assigned_bot} → {bot_type_lower}")
                await _webhook_cache.set(assigned_key, bot_type_lower, ttl=604800)
            else:
                # Stale API value — honour existing assignment
                bot_type_lower = assigned_bot
    else:
        await _webhook_cache.set(assigned_key, bot_type_lower, ttl=604800)
```

---

## Fix 4 — 30-Second Wait Before Adding Tags

### Root Cause (confirmed by code audit)

Tags are applied **inside** `process_seller/buyer_message()`, which runs
*before* the webhook calls `send_message()`. The exact call order is:

```
webhook handler
  └─ bot.process_seller_message()
       └─ _apply_ghl_actions()      ← tags added HERE (10s hard timeout)
            └─ ghl_client.add_tag() ← "seller_hot" added to contact NOW
  └─ ghl_client.send_message()      ← SMS sent AFTER tags already fired
```

This means GHL tag-triggered workflows (e.g., "seller_hot → send CMA report")
fire **before** the contact has received the SMS reply. The 30-second delay
ensures the SMS lands first, then automation follows.

### ⚠️ Why inline `asyncio.sleep(30)` won't work

Adding `await asyncio.sleep(30)` directly inside `_apply_ghl_actions()` would:
1. Exceed the existing 10-second `asyncio.wait_for()` wrapper → tags silently skipped
2. Block the webhook request for 30+ seconds → Render's HTTP timeout fires
3. Hold the `lock:{contact_id}` key for 30+ extra seconds → throttles follow-up messages

**The correct approach: FastAPI `BackgroundTasks`** — tags run 30 seconds
*after* the HTTP 200 is returned, so none of the above apply.

### Required Code Change — `jorge_seller_bot.py`

In `_apply_ghl_actions()` (around line 1139), add the delay before the
tag operations begin:

```python
async def _apply_ghl_actions(
    self,
    ghl_client: GHLClient,
    actions: List[Dict[str, Any]],
    contact_id: str,
) -> None:
    """Apply GHL actions with a 30-second pre-tag delay."""
    import asyncio

    tag_actions = [a for a in actions if a.get("type") in ("add_tag", "remove_tag")]
    non_tag_actions = [a for a in actions if a.get("type") not in ("add_tag", "remove_tag")]

    # Apply non-tag actions (custom field updates) immediately
    for action in non_tag_actions:
        try:
            await self._apply_single_action(ghl_client, action, contact_id)
        except Exception as e:
            self.logger.error(f"Non-tag action failed for {contact_id}: {e}")

    # Wait 30 seconds before applying tags so downstream GHL workflows
    # don't fire before the contact has received the SMS reply
    if tag_actions:
        self.logger.info(f"Waiting 30s before applying tags for {contact_id}")
        await asyncio.sleep(30)
        for action in tag_actions:
            try:
                await self._apply_single_action(ghl_client, action, contact_id)
            except Exception as e:
                self.logger.error(f"Tag action failed for {contact_id}: {e}")
```

Apply the **same pattern** to `buyer_bot.py` `_generate_actions` / apply logic.

### ⚠️ Render Timeout Consideration

The current implementation uses a **10-second hard timeout** for GHL actions
(to avoid Render's 30-second HTTP response timeout). Adding a 30-second
sleep inside the webhook request will cause a timeout.

**Solution:** Run the tag-application step in a background task, decoupled
from the HTTP response:

```python
# routes_webhook.py — after sending SMS reply (around line 257)

import asyncio

async def _apply_tags_after_delay(bot_result, contact_id, location_id):
    """Run tag application 30 seconds after the HTTP response is returned."""
    await asyncio.sleep(30)
    await bot_result.apply_deferred_tags()  # see note below

# Fire and forget — do not await
asyncio.create_task(
    _apply_tags_after_delay(result, contact_id, location_id)
)
```

This requires refactoring the bot result to expose a `apply_deferred_tags()`
coroutine. The simpler alternative (fewer refactor steps):

**Alternative — Deferred Tag List on SellerResult / BuyerResult:**

1. `SellerResult` and `BuyerResult` gain a `deferred_tag_actions: List[Dict]` field
2. The bot populates `deferred_tag_actions` with the tag add/remove operations
   but does NOT apply them immediately
3. `routes_webhook.py` fires a background task after returning HTTP 200:

```python
# In routes_webhook.py, after return {"status": "processed", ...}
# (use asyncio.ensure_future or background_tasks via FastAPI BackgroundTasks)

from fastapi import BackgroundTasks

@router.post("/api/ghl/webhook")
async def unified_ghl_webhook(request: Request, background_tasks: BackgroundTasks):
    ...
    # After SMS is sent and before HTTP response:
    if hasattr(result, "deferred_tag_actions") and result.deferred_tag_actions:
        background_tasks.add_task(
            _deferred_tag_apply,
            ghl_client=state._ghl_client,
            contact_id=contact_id,
            actions=result.deferred_tag_actions,
            delay_seconds=30,
        )

    return {"status": "processed", **result_meta}


async def _deferred_tag_apply(
    ghl_client, contact_id: str, actions: list, delay_seconds: int = 30
):
    """Background task: wait N seconds then apply tag actions."""
    await asyncio.sleep(delay_seconds)
    for action in actions:
        try:
            action_type = action.get("type")
            if action_type == "add_tag":
                await ghl_client.add_tag(contact_id, action["tag"])
            elif action_type == "remove_tag":
                await ghl_client.remove_tag(contact_id, action["tag"])
        except Exception as e:
            logger.error(f"Deferred tag action failed for {contact_id}: {e}")
```

FastAPI `BackgroundTasks` run **after** the HTTP response is sent, so this
does not affect the Render timeout. The 30-second sleep occurs server-side
after the client has already received `200 OK`.

---

## Implementation Order

```
1. Fix 1 (GHL config)     — No code change. Configure in GHL UI. Do first.
2. Fix 2 (verification)   — Test after Fix 1. Confirms pairing is correct.
3. Fix 3 (bot exclusivity) — Code change in routes_webhook.py (~20 lines)
4. Fix 4 (tag delay)      — Code change: deferred tag pattern (~40 lines)
```

---

## Files to Change

| File | Change | Lines Affected |
|------|--------|----------------|
| `bots/lead_bot/routes_webhook.py` | Bot-assignment exclusivity (Fix 3) | ~185–200 |
| `bots/lead_bot/routes_webhook.py` | `BackgroundTasks` deferred tag (Fix 4) | ~89, ~252–258 |
| `bots/seller_bot/jorge_seller_bot.py` | `deferred_tag_actions` on result + skip immediate tag apply | ~1068–1160 |
| `bots/buyer_bot/buyer_bot.py` | Same deferred tag pattern | ~636–703 |
| `bots/seller_bot/jorge_seller_bot.py` (`SellerResult`) | Add `deferred_tag_actions: List[Dict] = field(default_factory=list)` | ~160–170 |
| `bots/buyer_bot/buyer_bot.py` (`BuyerResult`) | Same | ~110–120 |
| `bots/lead_bot/routes_admin.py` | `/admin/reassign-bot` endpoint | new |

**GHL (no code — UI configuration only):**
- Create `Bot Type` custom field
- Create Seller Bot Relay, Buyer Bot Relay, Lead Bot Relay workflows
- Each inbound SMS workflow: filter by `Bot Type`, send webhook with `customData.bot_type`

---

## Test Plan

### Fix 1 + 2 — Correct bot fires, correct message

```bash
# Seller flow
curl -X POST https://jorge-realty-ai-xxdf.onrender.com/api/ghl/webhook \
  -H "Content-Type: application/json" \
  -d '{"contactId":"test-s1","locationId":"LOC","body":"I want to sell","customData":{"bot_type":"seller"}}'
# Expected: response_message asks about property CONDITION, not pre-approval

# Buyer flow
curl -X POST https://jorge-realty-ai-xxdf.onrender.com/api/ghl/webhook \
  -H "Content-Type: application/json" \
  -d '{"contactId":"test-b1","locationId":"LOC","body":"I want to buy","customData":{"bot_type":"buyer"}}'
# Expected: response_message asks about BEDS/BUDGET/AREA, not property condition
```

### Fix 3 — Only one bot active

```bash
# Attempt to activate seller bot on a buyer-assigned contact
curl ... '{"contactId":"test-b1","body":"test","customData":{"bot_type":"seller"}}'
# Expected: {"status":"skipped","reason":"bot_assignment_conflict"}
```

### Fix 4 — Tag delay

```bash
# Trigger a HOT buyer (pre-approved + ≤30 day timeline) and watch GHL tags
# Tags should NOT appear in GHL immediately after the SMS is sent
# They should appear ~30 seconds later
```

### Automated tests

```bash
# New tests to add
.venv/bin/python -m pytest tests/test_webhook_routing.py -v

# Full suite — still expect same 20 pre-existing failures
.venv/bin/python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/load
```

**New test file `tests/test_webhook_routing.py` should cover:**
- `test_seller_bot_type_routes_to_seller()` — `bot_type=seller` → seller SMS, never buyer Q
- `test_buyer_bot_type_routes_to_buyer()` — `bot_type=buyer` → buyer SMS, never seller Q
- `test_missing_bot_type_defaults_to_lead()` — missing field → lead analysis, no SMS
- `test_bot_assignment_exclusivity()` — second bot type rejected for same contact
- `test_bot_assignment_overridden_by_payload()` — explicit payload overrides stale assignment
- `test_deferred_tags_not_applied_immediately()` — tag apply task deferred, not instant

---

## Acceptance Criteria

- [ ] Buyer contact texts in → receives buyer qualification questions (beds, budget, area)
- [ ] Seller contact texts in → receives seller qualification questions (condition, price, motivation)
- [ ] Lead contact texts in → lead analysis runs, no SMS (unless lead bot has its own reply)
- [ ] A contact assigned to buyer bot does NOT trigger seller bot on the same message
- [ ] GHL tag `buyer_hot` / `seller_hot` appears in contact timeline ~30 seconds AFTER the SMS is delivered
- [ ] All 30 persona tests pass: `pytest tests/test_prospect_personas.py`
- [ ] No new failures in full test suite beyond the existing 20 pre-existing failures
