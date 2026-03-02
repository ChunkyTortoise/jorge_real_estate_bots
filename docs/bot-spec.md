# Jorge Real Estate Bots — Comprehensive Spec

> Living document. Last updated: 2026-03-01.
> Both bots must behave exactly as described here in production.

---

## Table of Contents

1. [Seller Bot Flow](#seller-bot-flow)
2. [Buyer Bot Flow](#buyer-bot-flow)
3. [Calendar Scheduling (Both Bots)](#calendar-scheduling-both-bots)
4. [GHL Routing Requirements](#ghl-routing-requirements)
5. [E2E Test Checklist](#e2e-test-checklist-manual)

---

## Seller Bot Flow

### Trigger
GHL webhook sends seller lead to **`POST /api/jorge-seller/process`**

### Question Sequence

| Step | Question | Notes |
|------|----------|-------|
| Q0 | Jorge greeting phrase (random from `JORGE_PHRASES`) + Q1 | First contact |
| Q1 | Property condition: needs major repairs / minor fixes / move-in ready | Classifies ARV discount |
| Q2 | Price expectation: "What do you think it's worth as-is?" | Anchors seller expectations |
| Q3 | Motivation to sell: job relocation / inherited / divorce / foreclosure / downsizing | Urgency signal |
| Q4 | Offer: cash offer at 75% ARV, 2-3 week close — does that work? | Conversion moment |

### Temperature Outcomes

| Temperature | Condition | Action |
|-------------|-----------|--------|
| **HOT** | Q4 accepted + timeline acceptable | Offer calendar slot (prose format, 2 options) |
| **WARM** | All 4 Qs answered + reasonable but not committed | Send fallback calendar message |
| **COLD** | <4 Qs answered or disqualifying responses | Continue nurturing sequence |

### Jorge-Active Tag
When the GHL contact has the `Jorge-Active` tag, **the bot silences itself completely** and takes no action.

---

## Buyer Bot Flow

### Trigger
GHL webhook sends buyer lead to **`POST /api/jorge-buyer/process`**

### Question Sequence

| Step | Question | Notes |
|------|----------|-------|
| Q0 | Jorge greeting phrase (random from `JORGE_BUYER_PHRASES`) + Q1 | First contact |
| Q1 | Preferences: beds, baths, sqft, price range, city/area | Must have beds OR price OR sqft to advance |
| Q2 | Financing: pre-approved or paying cash? | `preapproved=True` if approved or cash buyer |
| Q3 | Timeline: 0-30 days / 1-3 months / just browsing | Sets `timeline_days` |
| Q4 | Motivation to buy: new job, growing family, investment, first home, upgrade | Completes qualification |

### Temperature Scoring

| Temperature | Condition | Action |
|-------------|-----------|--------|
| **HOT** | `preapproved=True` + `timeline_days ≤ 30` | Offer calendar slot (prose format, 2 options) |
| **WARM** | Qualified but looser timeline (31-90 days) | Send fallback calendar message |
| **COLD** | Incomplete or `timeline_days > 90` / just browsing | Continue nurturing |

### Seller-Question Guardrail
The buyer bot **must never** ask about:
- Property condition
- What their home is worth
- Motivation to sell
- Cash offer acceptance

If the lead steers conversation seller-adjacent, Jorge redirects: *"Let's stay focused on finding you the right home to buy."*

### Jorge-Active Tag
When the GHL contact has the `Jorge-Active` tag, **the bot silences itself completely** and takes no action.

---

## Calendar Scheduling (Both Bots)

### Trigger Conditions
- Scheduling is triggered **once**, on the **first HOT classification**
- Re-triggered only if the lead has not yet confirmed a booking

### Service
`CalendarBookingService.offer_appointment_slots(contact_id, lead_type)`

- If `JORGE_CALENDAR_ID` is not set → returns `FALLBACK_MESSAGE` (no error)
- Fetches next 2 available slots from GHL calendar API
- **Cap:** Maximum 2 slots offered per message

### Slot Offer Format (Prose)
```
I have {slot1_display} or {slot2_display} open — which works better for you?
```
Example: *"I have Monday March 3rd at 10am or Tuesday March 4th at 2pm open — which works better for you?"*

> **Never use** "Reply with 1, 2, or 3" style formatting.

### Natural-Language Slot Detection
`detect_slot_selection(message, contact_id)` parses lead replies:

| Reply Pattern | Detected Slot |
|---------------|---------------|
| "first" / "1st" / "morning" / "option 1" | Slot 0 (first offered) |
| "second" / "2nd" / "afternoon" / "option 2" | Slot 1 (second offered) |
| Day name in reply (e.g., "Tuesday") | Matched against slot display text |
| Bare digit "1" or "2" | Legacy fallback to slot index |
| Ambiguous ("sure", "ok", "sounds good") | Returns `None` → bot re-offers or defers to Jorge |

### Booking Confirmation
On successful booking:
```
Perfect, I've got you down for {display_time}. Jorge will reach out to confirm.
```

---

## GHL Routing Requirements

| Requirement | Detail |
|-------------|--------|
| Seller leads | GHL workflow sends to `/api/jorge-seller/process` |
| Buyer leads | GHL workflow sends to `/api/jorge-buyer/process` |
| Bot Type field | GHL contact must have `Bot Type` custom field set to `"seller"` or `"buyer"` |
| Webhook auth | `GHL_WEBHOOK_SECRET` or `GHL_WEBHOOK_PUBLIC_KEY` env var required |
| Jorge-Active | Tag on contact silences the bot — must be set by Jorge in GHL |

### Required Environment Variables

| Variable | Purpose |
|----------|---------|
| `REDIS_URL` | State persistence between messages |
| `GHL_API_KEY` | GHL REST API authentication |
| `GHL_WEBHOOK_SECRET` or `GHL_WEBHOOK_PUBLIC_KEY` | Webhook signature verification |
| `JORGE_USER_ID` | Must be `4lAS80xUq4MIRbgfQ5vg` — matches GHL contact owner |
| `JORGE_CALENDAR_ID` | GHL calendar ID for slot booking (optional — fallback if unset) |
| `ANTHROPIC_API_KEY` | Claude API for response generation |

---

## E2E Test Checklist (Manual)

**Test phone:** `3109820492`
**Environment:** Production — `jorge-realty-ai-xxdf.onrender.com`

---

### Seller Bot Flow

1. Send **"I want to sell my house"**
   → Seller bot responds with Q1 (property condition)

2. Reply **"needs some work"**
   → Q2 (price expectation: "What do you think it's worth as-is?")

3. Reply **"$350k"**
   → Q3 (motivation: job relocation / inherited / divorce / etc.)

4. Reply **"relocating for work"**
   → Q4 (cash offer at 75% ARV, 2-3 week close)

5. Reply **"yes that works"**
   → Scheduling message with two prose time options (no "Reply 1, 2, or 3")

6. Reply **"the first one"**
   → Confirmation: "Perfect, I've got you down for [slot]. Jorge will reach out to confirm."

---

### Buyer Bot Flow

7. *(Reset lead / new contact)*
   Send **"looking to buy a home"**
   → Buyer bot responds with Q1 (preferences: beds, baths, sqft, price, area)

8. Reply **"3 bed 2 bath under 600k in Rancho"**
   → Q2 (pre-approval: "Are you pre-approved or paying cash?")

9. Reply **"yes pre-approved"**
   → Q3 (timeline: "0-30 days, 1-3 months, or just browsing?")

10. Reply **"within 30 days"**
    → Q4 (motivation to buy)
    *(Note: HOT classification triggered here — scheduling offer will be appended to Q4 response or next message)*

11. Reply **"job relocation"**
    → Q4 complete + scheduling message appended (prose format, 2 options)

12. Reply **"Tuesday works"**
    → Confirmation: "Perfect, I've got you down for [Tuesday slot]. Jorge will reach out to confirm."

---

### Verification Checklist

- [ ] Seller bot responds at step 1 within 10 seconds
- [ ] Buyer bot responds at step 7 within 10 seconds
- [ ] Calendar offer uses prose format (not "Reply 1, 2, or 3")
- [ ] "the first one" books slot 0 (seller flow)
- [ ] "Tuesday works" books correct day slot (buyer flow)
- [ ] Confirmation message references correct time slot display text
- [ ] No bot response when `Jorge-Active` tag is present
- [ ] Health endpoint returns 200: `curl https://jorge-realty-ai-xxdf.onrender.com/health`
