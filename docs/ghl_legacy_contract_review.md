# Jorge GHL Legacy Contract Review

- Location ID: `3xt4qayAh35BlDLaUv7P`
- Required tags missing: None
- Required fields missing: None
- Extra live tags count: `331`
- Extra live fields count: `608`

## Tag Review

- High-risk review candidates: actively home shopping, agent bot, ai off, ai-off, alabama buyer, appointment-buyer_consultation, bot-fallback-active, buyer, buyer 1 year fu, buyer 6 month fu, buyer activation sequence, buyer agent, buyer bot, buyer discovery, buyer discovery completed, buyer mia, buyer paused, buyer reactivated, buyer responded to 1 year fu, buyer responded to connected with lender, buyer response – needs review, buyer revive, buyer-first_time, buyer-investor, buyer-lead, buyer-relocator, buyer-upsizer, cold buyer lead revived, cold lead revived, cold-buyer, cold-lead, cold-seller, county record bot, dead lead, direct to buyer bot, direct to seller bot, duplicate lead, email 2 active, email 3 active, email 4 active, ... (108 total)
- Medium-risk review candidates: appointment booked, appointment set, appointment-listing_appointment, cold agent, cold call, cold follow up (auto-nurture), disqualified, follow up, future follow-up, hot, hot agent, insta follow-up needed, needs appointment set, needs cold call, needs underwriting(hot), no response follow up, qualified, tiktok follow up, unqualified, waiting for photos, warm agent
- Likely harmless or business-only: 1 deal, 1 year f-u, 1-3months, 10 day fu, 123 main st, 2 deal, 6 month f-u, 6-12months, 7 day fu, a2p form needed, a2p form submitted, add tag here, add tag-mobile tag, agent, agent unworkable, ai on, ai-on, alpha, already sold, assignment agreement sent, attention, auction niche, auto-booked, awaiting offer, bad number, banana street blast received, bought elsewhere, call again, cancelled, carrot, cash agreement sent, cathedreal city, christmas, closed, closed escrow, commercial / retail, connected with lender, contract signed, contractor, couldn't find caller name, ... (202 total)

## Field Review

- High-risk review candidates: AI Bot Trigger, AI Buyer Budget, AI Buyer Intent, AI Buyer Temperature, AI Chatbot Name, AI Handoff History, AI Last Bot, AI Lead Location, AI Lead Score, AI Lead Timeline, AI Seller Decision Maker, AI Seller Intent, AI Seller Liens, AI Seller Listing History, AI Seller Motivation, AI Seller Repairs, AI Seller Temperature, Bot Type, Buyer Baths Min, Buyer Beds Min, Buyer Location, Buyer Persona, Buyer Personality Type (2 required), Buyer Price Max, Buyer Price Min, Buyer Qualification, Buyer Sqft Min, Buyer Temperature, Buyer/Seller, CA Buyer Name on Contract, Cash Buyer Classification, Cash Buyer Location Preferences, Cash Buyer Price Range, Cash Buyer Property Choice (Choose One or Multiple), Cash Buyer Strategy, Lead Identity, Lead Notes, Lead Score, Lead Source, Lead Value Tier, ... (153 total)
- Medium-risk review candidates: AI Appointment Time, AI Appointment Type, AI Pre Approval Status, AI Price Expectation, AI Property Condition, AI Qualification Complete, AI Qualification Score, AI Timeline Urgency, AI Valuation Price, Agent Qualification, CA Contract Price, Cold Call Notes, Condition, Follow Up Due Date, Follow Up Due Date:, List the names of your Cold Callers (their American names), Marketing Integrations (PPL, PPC, Cold Call, etc), PSA Contract Price, Pre-Approval Status, Price, Price Expectation, Property Condition, Snapshot, Stripe Price ID, Timeline To Buy, Timeline Urgency, agent_qualification, ai_appointment_time, ai_appointment_type, ai_pre_approval_status, ai_price_expectation, ai_property_condition, ai_qualification_complete, ai_qualification_score, ai_timeline_urgency, ai_valuation_price, ca_contract_price, cold_call_notes, condition, contact cold call notes, ... (81 total)
- Likely harmless or business-only: AI Assistant is:, AI Conversation Context, AI FRS Score, AI PCS Score, AI Property Address, AI Property Preferences, AI Questions Answered, Account Tier, Anniversary, Are You Working With an Agent?, Are you a realtor or a wholesaler, Billing Status, Business Logo Image, CA Additional Terms, CA Assignor Name (Your Name or LLC), CA Closing Date, CA Earnest Money, CA Inspection End Date, CA Property Address for Contract, CA Title Company, Call Attempts, Call Transcript, Campaign Name, County, Coupon Used, Detected Persona, Do you have a Zapier Login?, Do you have any other companies that you acquire real estate with? *, Do you want a phone number for each of your markets (above)?, Do you want us to link your dialer to Lyrio?, Do you want us to port any phone numbers?, Domains & Domain Hosting Provider Login, Email 2, Email 3, Email 4, Email 5, Employer Identification Number (EIN), Expected ROI, Has a Deal?, How Soon Do You Plan to Buy/Sell?, ... (374 total)

## Review Guidance

- Treat every high-risk item as a manual audit candidate before handoff.
- Any legacy tag or field that influences routing, suppression, or workflow branching must be retired or explicitly accepted.
- Any legacy item that only serves reporting may remain if it does not create a parallel operator control path.

---

## App-Code-Confirmed Risk Classification (2026-03-07)

This section documents which legacy items the **app code actually reads**, versus items only used by GHL-side workflows. Based on code analysis of `bots/`.

### Critical: App reads these — must verify no GHL workflow writes them with conflicting values

| Field / Tag | App read path | Risk | Disposition |
|---|---|---|---|
| `Bot Type` (custom field, key `bot_type`) | `conversation_orchestrator.py:74,124` reads `custom_data.get("Bot Type")` and GHL contact custom fields. If set, it OVERRIDES app mode detection. | **CRITICAL** — Any workflow writing `Bot Type` redirects leads to the wrong bot | Must verify: either no workflow writes `Bot Type`, or it is only written by the app. If a workflow writes it, the workflow must be rewritten to send canonical `mode` in webhook payload instead. |
| `Jorge-Active` (tag, normalized: `jorge active`) | `conversation_contract.py:59-68` — checked by all three bots. Presence = human takeover, bot goes silent. | LOW (intended behavior) | Keep. This IS the sole manual takeover control. Normalize check is case/hyphen/underscore-insensitive. |

### GHL-only: Not read by app, but create parallel GHL-side control paths

| Tag / Field | GHL Use | App Impact | Disposition |
|---|---|---|---|
| `ai off` / `ai-off` | Triggers workflow `2. AI OFF/ON Tag Added` which writes `AI Assistant is:` field. Suppresses GHL-native AI assistant only. | None on Jorge app (app checks `Jorge-Active` only) | Accept as GHL-native control; confirm it does NOT disable the Jorge app webhook processing. |
| `ai on` / `ai-on` | Counter-tag to `ai off`. Fires same workflow to re-enable GHL AI assistant. | None on Jorge app | Accept. |
| `agent bot` / `buyer bot` / `direct to buyer bot` / `direct to seller bot` | Legacy bot-selection tags. May have triggered old workflows. | NOT read by app code (app does not check these tags for routing) | Verify no PUBLISHED workflow uses these to call an app endpoint. If found, disable/rewrite that workflow. |
| `AI Last Bot` | Was set by old system to track which AI last handled. | NOT read by app | Harmless if not written by any active workflow. Retire eventually. |
| `AI Bot Trigger` | Old trigger mechanism. | NOT read by app | Must verify not used by any published workflow trigger. |
| `Buyer/Seller` (custom field) | Old bot-selection field. | NOT read by app (app reads `bot_type` / `Bot Type` only) | Accept if not written by active workflows. |
| `Lead Identity` | Old classification field. | NOT read by app | Accept if not written by active workflows. |
| `bot-fallback-active` | Signals old fallback routing. | NOT read by app | Verify no active workflow sets this to redirect messages away from Jorge. |

### Required follow-up before handoff

1. **Verify `Bot Type` field**: Check live GHL contacts — does any have `Bot Type` set? If yes, is the value intentional? If no, the risk is moot for current contacts but any workflow that writes it must be identified and stopped.
2. **Verify `agent bot` / `buyer bot` / `direct to *` tags**: Check if any PUBLISHED workflow has a trigger on these tags that routes to a separate endpoint or sends its own AI message.
3. **Verify `AI Bot Trigger` field**: Check if any published workflow reads this field value and branches on it.
