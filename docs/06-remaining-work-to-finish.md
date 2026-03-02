REMAINING WORK — WHAT NEEDS TO HAPPEN TO CALL THIS DONE
=========================================================
For: Internal — Cayman Roden
Date: February 26, 2026


This is the complete list of open items. Everything on this list has a clear next action.
Grouped by owner.


========================================
JORGE'S SIDE (BLOCKERS — SYSTEM CANNOT RUN WITHOUT THESE)
========================================

Item 1: Top up Anthropic API credits
    Where: console.anthropic.com/settings/billing
    Why: Claude credits exhausted. Bots are in fallback scripted mode.
         Everything works but responses are generic instead of Jorge's voice.
    Who: Jorge only — account is in his name.
    Effort: 5 minutes, ~$20-50.

Item 2: A2P 10DLC SMS registration
    Where: GHL Settings > Phone Numbers > A2P Registration
    Why: Required for US SMS since Feb 2025. Without it, outbound texts
         may be silently dropped or spam-flagged by carriers.
    Who: Jorge with his phone/SMS provider or via GHL support.
    Effort: 30 minutes to submit. 1-4 weeks to clear.

Item 3: GHL workflow edit — "New Inbound Lead"
    Steps: Documented in email and in 02-ghl-setup-guide.md
    Effort: 5 minutes.
    Status: Not done yet.

Item 4: GHL workflow edit — "5. Process Message - Which Bot?"
    Steps: Documented in email and in 02-ghl-setup-guide.md
    Effort: 5 minutes.
    Status: Not done yet.

Item 5: GHL custom fields — create all 12
    Steps: Documented in 02-ghl-setup-guide.md, Part 1
    Effort: 10 minutes.
    Status: Not done yet.

Item 6: GHL webhooks — create both inbound webhooks
    Steps: Documented in 02-ghl-setup-guide.md, Part 2
    Effort: 5 minutes.
    Status: Not done yet.

Item 3b: Set Bot Type field on existing contacts
    What: Any contacts already in GHL need their Bot Type field set manually
          (seller or buyer) so the system routes them correctly.
    Who: Jorge — bulk edit in GHL or set individually.
    Effort: 5-15 minutes depending on contact count.


========================================
CAYMAN'S SIDE — DEPLOYMENT
========================================

Item 8: Confirm Redis is connected
    What: The Render service falls back to in-memory cache if Redis rejects
          the connection (IP allowlist issue). In-memory cache works but resets
          on restart, which means conversations are lost on every deploy.
    How: Check Render logs for "Redis connected" vs "Using MemoryCache fallback."
         If fallback: allow Render outbound IPs in Redis dashboard, or switch to
         a Redis provider with no IP restriction (Upstash recommended — free tier).
    Status: Currently running on MemoryCache fallback.
    Effort: 30 minutes to switch to Upstash if needed.
    Priority: Medium. System works without it but conversations reset on restart.

Item 9: Wire Lyrio Dashboard to live GHL data
    What: Add Jorge's GHL API key to Streamlit secrets.
          Change the data provider from DemoDataProvider to live GHL client.
    How: Streamlit Cloud > App Settings > Secrets > add ghl_api_key.
         One config change in command_center/data_provider.py.
    Status: Dashboard is live on demo data.
    Effort: 30 minutes.
    Priority: Low until Jorge reviews the demo and confirms he wants live data.

Item 10: Database migration
    What: The database schema exists (Alembic migrations written).
          Production DB has not been migrated. Currently all state is in cache only.
    Why this matters: If the Render service restarts and Redis is down, all
          active conversations are lost. DB migration gives persistent fallback.
    How: Run alembic upgrade head against the production database.
    Status: Deferred.
    Effort: 1-2 hours (migration + verification).
    Priority: Low for MVP. Revisit if Render restarts cause customer issues.


========================================
CAYMAN'S SIDE — VERIFICATION AFTER DEPLOY
========================================

Item 11: End-to-end smoke test after deploy
    What: After pushing fixes and Jorge completes GHL setup, run a live test:
          1. Send a test SMS to Jorge's GHL number from a new contact
          2. Confirm webhook fires (check Render logs)
          3. Confirm Lead Bot responds
          4. Reply "I want to sell"
          5. Confirm seller_bot tag applied in GHL
          6. Confirm Seller Bot starts Q1
          7. Answer all 4 questions
          8. Confirm temperature tag written to GHL contact
          9. Confirm custom fields populated in GHL contact
    Status: Cannot run until Jorge completes GHL setup (Items 3-6).
    Effort: 30 minutes.

Item 12: Confirm CMA workflow trigger (optional)
    What: Score a test lead HOT and confirm CMA Report Generation workflow
          fires in GHL. If it does not fire, the workflow needs to be created
          or the trigger name needs to match.
    Status: Deferred until smoke test passes.

Item 13: Invoice Jorge for today's work
    What: Today's session was correction work beyond the original scope —
          12 bugs, scope alignment, documentation package, test coverage additions.
    Options:
          Include in original invoice as scope adjustment.
          Separate invoice for correction and documentation work.
          Good-faith no-charge if relationship warrants it.
    Status: Decision pending.


========================================
SCOPE DECISIONS PENDING FROM JORGE
========================================

Item 14: Which enterprise features to activate (if any)
    What: Full inventory in 04-enterprise-dev-beyond-spec.md.
    Jorge needs to decide: activate any, all, or none of the features
    built beyond the original agreement.
    Each has an activation effort estimate in that document.
    Recommendation: Get the basic system live and working first.
    Then decide on CMA delivery, scheduling, and follow-up cadence as phase 2.

Item 15: Lyrio Dashboard — keep or drop
    What: Dashboard is live at lyrio-jorge.streamlit.app.
          It costs nothing to keep running (Streamlit free tier).
          Wiring to live GHL data is 30 minutes.
    Jorge should decide if he wants to use it or if it adds complexity he does not need.


========================================
DONE — NO ACTION NEEDED
========================================

    3 bots coded, tested (552 tests), deployed to Render
    Production URL live and responding
    All 12 production bugs fixed
    GHL API client working (tag add, tag remove, field update, SMS send)
    Temperature scoring correct (urgency-weighted, all edge cases tested)
    Conversation history working in both bots
    First-message preservation working
    Cache failure resilience working
    Stale state compatibility working
    Price extraction edge cases handled
    Lyrio Dashboard live on demo data
    All documentation in this package complete
    Deploy fixes pushed to main on 2026-03-01 — Render auto-deployed (552 tests, 0 failures)
    Webhook routing: bot exclusivity (Fix 3), 30s deferred tags (Fix 4)
    /admin/reassign-bot endpoint live
    30 persona tests + 8 webhook routing tests added
    Service area updated: Dallas → Inland Empire (Rancho Cucamonga)
