GHL SETUP GUIDE — WHAT JORGE NEEDS TO CONFIGURE
================================================
For: Jorge Salazar
Purpose: Complete GoHighLevel configuration required to connect the bots to your account


This guide covers every step required in GoHighLevel to wire up the three bots. The bots are already live and running. This is the GHL side of the connection.

There are 4 parts:
    1. Create the custom contact fields (once, 10 minutes — 13 fields total)
    2. Set up the two inbound webhooks (once, 5 minutes)
    3. Edit two existing workflows (already documented in the email — 5 minutes each)
    4. Optional: Create pipeline stages for bot-driven lead scoring


========================================
PART 1 — CREATE CUSTOM CONTACT FIELDS
========================================

These fields are how the bots write information back into your GHL contacts. After every conversation, the bots update these fields automatically. Without them, the bot still runs, but none of the data gets saved to the contact record.

Navigate to: Settings > Custom Fields > Contact Fields > Add Field


BOT ROUTING FIELD — CREATE THIS FIRST

Field 1
    Label: Bot Type
    Internal Key: bot_type
    Type: Dropdown
    Options: lead, seller, buyer
    (CRITICAL: This field tells the system which bot handles the contact.
     Set to "seller" for seller leads, "buyer" for buyer leads.
     Without it, no bot replies.)


SELLER BOT FIELDS — CREATE ALL 5

Field 2
    Label: Seller Temperature
    Internal Key: seller_temperature
    Type: Text
    (Will contain: hot, warm, or cold)

Field 3
    Label: Seller Questions Answered
    Internal Key: seller_questions_answered
    Type: Number
    (Will contain: 0 through 4)

Field 4
    Label: Property Condition
    Internal Key: property_condition
    Type: Text
    (Will contain: needs_major_repairs, needs_minor_repairs, or move_in_ready)

Field 5
    Label: Seller Price Expectation
    Internal Key: seller_price_expectation
    Type: Number
    (Will contain: dollar amount seller stated)

Field 6
    Label: Seller Motivation
    Internal Key: seller_motivation
    Type: Text
    (Will contain: job_relocation, foreclosure, divorce, inheritance, downsizing, etc.)


BUYER BOT FIELDS — CREATE ALL 7

Field 7
    Label: Buyer Temperature
    Internal Key: buyer_temperature
    Type: Text
    (Will contain: hot, warm, or cold)

Field 8
    Label: Buyer Beds Minimum
    Internal Key: buyer_beds_min
    Type: Number

Field 9
    Label: Buyer Baths Minimum
    Internal Key: buyer_baths_min
    Type: Number

Field 10
    Label: Buyer Sqft Minimum
    Internal Key: buyer_sqft_min
    Type: Number

Field 11
    Label: Buyer Price Minimum
    Internal Key: buyer_price_min
    Type: Number

Field 12
    Label: Buyer Price Maximum
    Internal Key: buyer_price_max
    Type: Number

Field 13
    Label: Buyer Location
    Internal Key: buyer_location
    Type: Text
    (Will contain: Rancho Cucamonga, Upland, Fontana, Ontario, or Chino Hills)


NOTE ON FIELD NAMES: The Internal Key values above must be entered exactly as shown — lowercase, with underscores. These are case-sensitive. The Label (display name) can be whatever you want.


========================================
PART 2 — CREATE THE TWO INBOUND WEBHOOKS
========================================

These webhooks are how GHL sends information TO the bots. There are exactly two. One fires when a new contact is created. The other fires when any inbound message arrives.

Navigate to: Settings > Integrations > Webhooks > Add Webhook


WEBHOOK 1 — NEW CONTACT

    Name: Jorge Bots - New Lead
    URL: https://jorge-realty-ai-xxdf.onrender.com/ghl/webhook/new-lead
    Events to send: Contact Created
    Method: POST
    Status: Enabled


WEBHOOK 2 — INCOMING MESSAGES

    Name: Jorge Bots - Inbound Message
    URL: https://jorge-realty-ai-xxdf.onrender.com/api/ghl/webhook
    Important: If using GHL Workflow "Send Webhook" action, include this in Custom Data:
        bot_type: {{contact.bot_type}}
    Events to send: Inbound Message (or "Conversation Message Created" depending on your GHL version)
    Method: POST
    Status: Enabled


After saving both, send yourself a test SMS from a new contact and confirm in the bot dashboard (lyrio-jorge.streamlit.app) that a conversation appeared. If it shows up, the webhooks are connected.


========================================
PART 3 — WORKFLOW EDITS (ALREADY DOCUMENTED)
========================================

These two edits are covered in the main update email. Repeating here for completeness.

Edit 1: Workflow "New Inbound Lead"
    - Step 0: Add an "Update Contact Field" action BEFORE the webhook
        Set field: Bot Type = seller
        (This must run before the webhook fires so the bot knows it's a seller lead)
    - Find the "None" branch (far right)
    - Click existing Add Tag step
    - Add tag: lead-bot
    - Save and Publish

Edit 2: Workflow "5. Process Message - Which Bot?"
    - Step 0: Add an "Update Contact Field" action BEFORE the webhook
        Set field: Bot Type = buyer
        (This must run before the webhook fires so the bot knows it's a buyer lead)
    - Find the first If/Else "None" branch (far right)
    - Click existing Add Tag step
    - Add tag: lead-bot
    - Save and Publish


========================================
PART 4 — OPTIONAL: PIPELINE STAGES
========================================

The bots assign temperature scores (hot, warm, cold) to every lead. If you want those scores to also move contacts through a GHL pipeline, you can create pipeline stages that match. This is optional — the bots work without it. You would just use the custom fields and tags instead of pipeline view.

If you want the pipeline view:

Navigate to: CRM > Pipelines > Create Pipeline

Suggested pipeline name: AI Lead Scoring

Stages (in order):
    1. New Lead
    2. Hot — Ready Now
    3. Warm — Follow Up This Week
    4. Cold — Nurture
    5. Appointment Scheduled
    6. Under Contract
    7. Closed

The bots do not automatically move contacts through pipeline stages in the current deployment. That would require one additional workflow per stage using the temperature tags as triggers. Let me know if you want that set up.


========================================
TAGS USED BY THE BOTS (REFERENCE)
========================================

The bots apply and remove these tags automatically. You do not need to create them in advance — GHL creates tags on first use. This is just so you know what to expect when reviewing contacts.

Lead Bot Tags:
    lead-bot — assigned to unclassified leads for the lead bot to handle

Seller Bot Tags:
    seller_hot — seller scored HOT
    seller_warm — seller scored WARM
    seller_cold — seller scored COLD

Buyer Bot Tags:
    buyer_hot — buyer scored HOT
    buyer_warm — buyer scored WARM
    buyer_cold — buyer scored COLD
