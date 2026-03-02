THE DEPLOYED SYSTEM — HOW IT WORKS RIGHT NOW
=============================================
For: Jorge Salazar
Purpose: Exact technical flow of the three bots currently running in production


The bots are live at:
    https://jorge-realty-ai-xxdf.onrender.com

This is a single service running on Render (a cloud hosting platform). All three bots — Lead Bot, Seller Bot, and Buyer Bot — run inside this one process. GHL talks to it via webhooks. The service talks back to GHL via the GHL API.


========================================
HOW A CONVERSATION FLOWS — STEP BY STEP
========================================

Step 1: Lead texts in
    A lead sends an SMS to your GHL phone number. GHL receives it.

Step 2: GHL fires a webhook
    GHL sends the message content, contact ID, and contact details to:
    https://jorge-realty-ai-xxdf.onrender.com/api/ghl/webhook

Step 3: Message router decides which bot handles it
    The service checks the contact's existing tags and custom fields to determine
    which bot owns this conversation:
        - Has tag seller_hot, seller_warm, or seller_cold → Seller Bot
        - Has tag buyer_hot, buyer_warm, or buyer_cold → Buyer Bot
        - Has tag lead-bot or no bot tag yet → Lead Bot

Step 4: The correct bot processes the message
    The bot loads the full conversation history from cache (last 10 messages),
    determines what stage the conversation is in (which question they're on),
    and generates a reply in your voice using Claude AI.

    If Claude AI is unavailable (credits exhausted or API error):
        The bot falls back to a scripted re-ask of the current question.
        No conversation dies silently.

Step 5: Bot sends reply via GHL
    The bot calls the GHL API to send the reply as an SMS from your GHL number.
    The lead sees a normal text message from you.

Step 6: Bot updates the contact record in GHL
    The bot immediately updates the contact's:
        - Temperature tag (seller_hot, seller_warm, buyer_cold, etc.)
        - Custom fields (seller_temperature, property_condition, buyer_beds_min, etc.)

Step 7: Conversation stored in cache
    The full exchange is saved in cache with a 7-day expiration.
    The next time this lead texts, the bot picks up exactly where it left off.


========================================
NEW CONTACT FLOW — WHAT HAPPENS FIRST
========================================

When a brand new contact is created in GHL (not a reply — a first touch):

Step 1: GHL fires a "Contact Created" webhook to:
    https://jorge-realty-ai-xxdf.onrender.com/ghl/webhook/new-lead

Step 2: Lead Bot receives the new contact
    It checks if the contact has a seller or buyer tag already.
    If yes → routes to that bot immediately.
    If no → Lead Bot handles the initial engagement.

Step 3: Lead Bot sends the opening message
    "Hey [name]! Are you looking to buy or sell in [area]?"

Step 4: Lead replies → goes through message router (Step 2 above)
    Once the lead says "sell" or "buy," they are routed to the appropriate bot
    and tagged accordingly. Lead Bot steps aside.


========================================
THE THREE BOTS — WHAT EACH ONE DOES
========================================

LEAD BOT
    Purpose: First contact. Determine intent. Route to seller or buyer bot.

    Triggers:
        New contact created in GHL (via /ghl/webhook/new-lead)
        Any inbound message from a contact with the lead-bot tag

    What it does:
        Asks if they are buying or selling.
        Detects keywords (sell, buy, house, cash, looking, etc.)
        Routes to Seller or Buyer bot.
        If intent is unclear after 2 exchanges, asks directly.

    What it writes to GHL:
        Adds tag: lead-bot (while routing is in progress)
        Removes lead-bot tag once routed to seller or buyer bot


SELLER BOT
    Purpose: Qualify sellers with 4 questions. Score temperature. Trigger CMA for HOT leads.

    Triggers:
        Any inbound message from a contact with a seller tag

    What it does:
        Runs 4-question qualification sequence (condition, price, motivation, offer)
        Scores temperature after each exchange
        Sends offer at 75% of stated price at Question 4
        HOT leads trigger CMA Report Generation workflow in GHL

    What it writes to GHL after every message:
        Tags: seller_hot, seller_warm, or seller_cold (stale tag removed first)
        Fields: seller_temperature, seller_questions_answered, property_condition,
                seller_price_expectation, seller_motivation


BUYER BOT
    Purpose: Qualify buyers with 4 questions. Score temperature. Match properties.

    Triggers:
        Any inbound message from a contact with a buyer tag

    What it does:
        Runs 4-question qualification sequence (preferences, pre-approval, timeline, motivation)
        Scores temperature after each exchange
        HOT leads (pre-approved + 30-day timeline) marked QUALIFIED
        Runs property match against database after Question 1

    What it writes to GHL after every message:
        Tags: buyer_hot, buyer_warm, or buyer_cold
        Fields: buyer_temperature, buyer_beds_min, buyer_baths_min, buyer_sqft_min,
                buyer_price_min, buyer_price_max, buyer_location


========================================
INFRASTRUCTURE — WHAT IS RUNNING WHERE
========================================

Bot Service
    Host: Render (render.com)
    Service ID: srv-d6d5go15pdvs73fcjjq0
    URL: jorge-realty-ai-xxdf.onrender.com
    What it runs: Lead Bot + Seller Bot + Buyer Bot (all in one process)
    Memory: Spins down after 15 minutes of inactivity on free plan (cold start ~30 seconds)

Cache (Conversation Memory)
    Primary: Redis (if IP allowlist permits the Render IP)
    Fallback: In-process memory cache (resets on restart)
    TTL: 7 days per conversation

Database
    Present in codebase but schema not yet migrated to production.
    Currently all conversation state lives in cache only.
    Persistent storage across restarts requires Redis or DB migration (see remaining work doc).

AI Engine
    Provider: Anthropic (Claude)
    Model: claude-sonnet-4-6
    Usage: Generates bot replies, classifies seller answers, extracts buyer preferences
    Current status: Credits exhausted — bots in fallback mode (scripted replies only)

GHL Connection
    All GHL reads and writes use the GHL REST API v2.
    Auth: GHL API key stored in Render environment variables (never in code)


========================================
WHAT IS NOT CONNECTED YET
========================================

These are features that exist in the codebase but are not yet active in production:

    CMA Report delivery — logic exists, PDF generation and email delivery not wired to production
    GHL Calendar scheduling — booking logic exists, not connected to your calendar
    Buyer Property Alert workflow — exists in GHL spec, not yet triggered by bot
    Lead follow-up sequences (Day 3, 7, 30) — logic exists, scheduler not deployed
    Database persistence — schema exists, not migrated to production DB
    Lyrio Dashboard live data — currently shows demo data, not wired to your GHL account
