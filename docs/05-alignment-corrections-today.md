ALIGNMENT WORK COMPLETED — FEBRUARY 26, 2026
=============================================
For: Jorge Salazar
Purpose: Record of all corrections made today to bring the system into alignment with the agreed scope


This document covers two things: (1) what was wrong and why, and (2) everything that was corrected today. All 454 automated tests pass as of this writing.


========================================
WHY CORRECTIONS WERE NEEDED
========================================

The original development was done in two phases. Phase 1 built the enterprise platform described in the "beyond spec" document — the full lead intelligence system, Lyrio Dashboard, advanced analytics, and all three full-mode bots. Phase 2 was supposed to strip that down to the agreed scope: three simple bots, 4-question sequences, GHL integration.

The problem was that Phase 2 reused Phase 1 code rather than rebuilding clean. As a result, several enterprise features were partially connected, partially broken, or running in states that assumed infrastructure (database, Redis, calendar) that was not present in the production deployment. This created a class of bugs that only surfaced under real production conditions — not in local testing.

Today's work identified and fixed all of those bugs and confirmed the system is clean for production.


========================================
SCOPE ALIGNMENT CHANGES
========================================

The following enterprise features were confirmed disabled or deferred to keep the deployed system clean:

    Database persistence — schema exists, migration deferred. All state runs in cache only.
    Lead follow-up scheduler — coded and tested, not deployed. No background task runner in production.
    CMA PDF generation and email delivery — logic exists, not wired to production email.
    GHL Calendar integration — booking logic exists, not connected to your calendar.
    Buyer Property Alert workflow trigger — exists, not yet connected to a GHL workflow.
    Lyrio Dashboard live data — configured for demo data only until GHL key is provided.
    Retell AI voice calls — integration coded, not activated.
    Predictive analytics — coded, not running in production process.
    A/B testing — coded, experiments not initialized.

None of this was deleted. All of it can be activated as a separate scoped engagement.


========================================
THE 12 PRODUCTION BUGS FIXED TODAY
========================================

These were real defects that would have caused silent failures, wrong data, or dead-end conversations in production.


Fix 1: Buyer bot had no memory between messages
    Root cause: The buyer bot was building a Claude AI prompt without including
    any prior conversation turns. Each call to Claude started from scratch.
    Result: Claude could not reference anything said earlier. Buyers would repeat
    themselves and the bot would not notice.
    Fix: Added conversation history injection — passes the last 10 turns to Claude
    on every call, exactly as the seller bot already did.
    Tests added: 3 tests confirming history is passed and truncated correctly.

Fix 2: First message from leads was discarded (both bots)
    Root cause: The webhook handler processed the incoming message and immediately
    stored it in the outgoing response log, but the first message was never added
    to the conversation history before Claude was called.
    Result: If a lead said "I want to sell my house at 123 Elm, needs major repairs"
    in their first message, all of that context was gone before Claude saw it.
    Fix: First message is now added to conversation history before processing begins.
    Tests added: 2 tests confirming first message is preserved in both bots.

Fix 3: Seller bot sent a dead-end reply at Question 4 on AI failure
    Root cause: When Claude failed (credits exhausted or API error), the seller bot's
    fallback at Question 4 was a generic "give me a few" phrase that did not include
    the calculated offer amount. The conversation had no path forward.
    Result: Leads who texted back during an API outage got a dead-end message at
    the most critical moment — the cash offer.
    Fix: Fallback at Question 4 now re-asks the offer question with the correctly
    calculated amount at 75% of stated price.
    Tests added: 1 test for fallback path at each question stage.

Fix 4: GHL tag removal was calling the wrong API endpoint
    Root cause: The GHL API v2 requires tag removal via a JSON body POST request.
    The code was constructing the tag ID into the URL path, which returns 404 silently.
    Result: When a lead went from seller_warm to seller_hot, the old seller_warm tag
    was never removed. Contacts accumulated stale temperature tags. GHL automations
    triggered on wrong tags.
    Fix: Updated to use JSON body format as specified in GHL API v2 documentation.
    Tests added: 2 tests confirming tag add and tag remove use correct request format.

Fix 5: Seller urgency was measured but not used in scoring
    Root cause: The urgency classifier (high/medium/low) ran correctly and returned
    a value, but the temperature scoring function never read it. The variable was
    extracted and then ignored.
    Result: A homeowner facing foreclosure (high urgency) and a homeowner with no
    timeline (low urgency) received identical temperature scores if their other
    answers were the same.
    Fix: Scoring function now reads urgency. High urgency boosts borderline COLD to WARM.
    Low urgency drops borderline WARM to COLD.
    Tests added: 4 tests covering each urgency-temperature interaction.

Fix 6: Seller bot used the wrong timezone
    Root cause: Timestamp generation used Python's datetime.now() which returns
    server local time. Render's servers run on UTC but this is not guaranteed
    across deploys. The database schema uses UTC timestamps.
    Result: Timestamp mismatches between cache entries and any database writes,
    and between different servers if load was distributed.
    Fix: All timestamp generation now uses datetime.utcnow() explicitly.
    Tests added: 1 test confirming UTC output.

Fix 7: Buyer price extraction read zip codes and city names as prices
    Root cause: The price extraction regex was too permissive. It matched any
    sequence of digits, which meant "McKinney 75069" would match "75069" as a
    price, and "Allen TX" contained "TX" which is a valid abbreviation but not
    a price signal.
    Result: "3 beds in McKinney 75069 under 500k" produced a buyer_price_max
    of $75,069 instead of $500,000.
    Fix: Price regex now requires an explicit price signal — a dollar sign prefix,
    a "k" or "K" suffix, or a standalone 6-plus digit number.
    Tests added: 8 tests covering city names, zip codes, valid prices, and edge cases.

Fix 8: Buyer bot crashed on cache write failure
    Root cause: The buyer bot's state-save block had no error handling. The seller
    bot had been updated with try/except previously, but the buyer bot was missed.
    Result: Any Redis hiccup — timeout, connection reset, eviction — during a buyer
    conversation would raise an unhandled exception and return a 500 to GHL,
    causing GHL to retry the webhook and potentially double-respond.
    Fix: Wrapped cache write in try/except with logging, matching seller bot pattern.
    Tests added: 1 test simulating cache failure during buyer conversation.

Fix 9: Seller bot showed "1 question answered" before any question was answered
    Root cause: The questions_answered counter was incremented when the conversation
    was initialized, before the first question was even asked.
    Result: The GHL custom field seller_questions_answered showed 1 immediately after
    the opening message, before the seller had answered anything.
    Fix: Removed the initialization increment. Counter now starts at 0 and increments
    only when a question response is actually classified.
    Tests added: 1 test confirming counter is 0 at conversation start.

Fix 10: Both bots crashed on deploy if any lead had cached state from an older version
    Root cause: When a new version of the code added or renamed a state field,
    cached state from the old version would cause a Pydantic validation error
    on load. Any lead mid-conversation at deploy time would get an unhandled exception.
    Result: Deploys broke active conversations. GHL would receive 500 errors and retry,
    causing double messages or silent failures.
    Fix: State loading now filters cached data to only known fields before instantiation.
    Unknown fields from old versions are dropped silently. Conversation continues.
    Tests added: 2 tests simulating stale cache state with missing and extra fields.

Fix 11: Seller bot silently reset temperature to cold on double-failure
    Root cause: A try/except block caught an error during temperature scoring,
    and the except clause defaulted the temperature to "cold" without logging
    the original error.
    Result: Leads would appear in GHL as cold with no trace of why. The underlying
    error (a bad API response, a corrupted state, a None value) was swallowed.
    Fix: Except clause now logs the full error with contact ID before falling back.
    Existing temperature is preserved instead of reset.
    Tests added: 1 test confirming error is logged and state is preserved.

Fix 12: Conversation history grew without limit in cache
    Root cause: Every incoming and outgoing message was appended to the cached
    conversation history list with no cap. Long conversations would grow to
    hundreds of entries.
    Result: Cache entries grew large over time. Claude AI received large prompts
    (which is expensive and slow) even though it only needs the last 10 turns.
    Fix: History list is now trimmed to the last 20 entries on every save.
    Claude still receives last 10. Cache entries stay bounded.
    Tests added: 1 test confirming history is trimmed after 20 entries.


========================================
TEST COVERAGE SUMMARY
========================================

Total tests: 454
All passing: Yes
Coverage: Seller bot, buyer bot, lead bot, GHL client, cache layer, state management,
          scoring functions, price extraction, tag management, webhook handling

Notable new test areas added today:
    Conversation history injection (buyer bot)
    First-message preservation (both bots)
    Urgency-temperature interaction (seller bot)
    Cache failure resilience (buyer bot)
    Stale state compatibility (both bots)
    Price extraction edge cases (buyer bot)
    Tag removal API format (GHL client)
