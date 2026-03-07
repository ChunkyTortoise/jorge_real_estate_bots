# Jorge GHL Contract Validation Report

- Overall result: `pass`

## Tags

- Missing required tags: None
- Extra live tags in export: 1 deal, 1 year f-u, 1-3months, 10 day fu, 123 main st, 2 deal, 6 month f-u, 6-12months, 7 day fu, a2p form needed, a2p form submitted, actively home shopping, add tag here, add tag-mobile tag, agent, agent bot, agent unworkable, ai off, ai on, ai-off, ... (331 total)

## Custom Fields

- Missing required fields: None
- Extra live fields in export: AI Appointment Time, AI Appointment Type, AI Assistant is:, AI Bot Trigger, AI Buyer Budget, AI Buyer Intent, AI Buyer Temperature, AI Chatbot Name, AI Conversation Context, AI FRS Score, AI Handoff History, AI Last Bot, AI Lead Location, AI Lead Score, AI Lead Timeline, AI PCS Score, AI Pre Approval Status, AI Price Expectation, AI Property Address, AI Property Condition, ... (608 total)

## Workflow Review

- Blockers: None
- Warnings: None

| Workflow | Trigger | Sends Messages | Writes Tags | Writes Fields | Moves Pipeline | Routing Logic | Conflict Risk | Disposition | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| "For Seller" Disposition Changed | UNKNOWN - inspect in GHL UI | no | no | no | yes | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests pipeline/opportunity mutation. |
| #1 Inbound Lead Force Call | UNKNOWN - inspect in GHL UI | yes | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. |
| #2 Double Tap Retry | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| #3 Failed Connections -> Send to Seller Activation Sequence | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| 1. Bot Change | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| 1A. LyrioAILeads to STB to Spintax Workflows(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| 1B. AGENT OUTREACH-Outbound Initial SMS (SPINTAX)(WAITING) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| 1C. FSBO-Outbound Initial SMS (SPINTAX)(WAITING) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| 1D. ARE YOU THE OWNER?-Outbound Initial SMS (SPINTAX)(WAITING) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| 1E. LAND-Outbound Initial SMS (SPINTAX)(WAITING) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| 2. AI OFF/ON Tag Added -> AI Assistant is: (Custom Field Change) | UNKNOWN - inspect in GHL UI | no | yes | yes | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests custom-field mutation. Name suggests tag mutation. |
| 2. Outbound 2nd Text Message (SPINTAX) FOR ALL(WAITING) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| 3. AI Assistant ->On and Off Tag Removal | UNKNOWN - inspect in GHL UI | no | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests tag mutation. |
| 4. Outreach 1st message | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| 5. Process Message - Which Bot? | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| 50%OFF | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| 6. Catch Unknown Inbound SMS | UNKNOWN - inspect in GHL UI | yes | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. |
| A2P Registration complete/not(AGENCY) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| AI BOT(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| AI Bot - Jorge Qualification | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| AI Bot Trigger Automation Dropdown(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| AI Outbound CAll ( Vapi- jennifer)(WAITING) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| ATP AI Inbound Call Answered | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| Add Cold Call/Seller Notes to Notes | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Agent Lead Form Submitted(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Agent Qualification Field Updated(WAITING) | UNKNOWN - inspect in GHL UI | no | no | yes | no | no | no | keep | Auto-generated from workflow name only. Name suggests custom-field mutation. |
| Ai Contact change Workflow | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Alert Team Member When Task Assigned | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Appointment Booked in Calendar | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Appointment Booked in Calendar | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Appointment Confirmation + Reminder(WAITING) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| Assign to Dispo manager | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Assign to lease option | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Auto Update Fields | UNKNOWN - inspect in GHL UI | no | no | yes | no | no | no | keep | Auto-generated from workflow name only. Name suggests custom-field mutation. |
| Buyer Qualification Field Updated(AGENCY) | UNKNOWN - inspect in GHL UI | no | no | yes | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests custom-field mutation. |
| Buyers IVR | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Call Again Manual Action Tag | UNKNOWN - inspect in GHL UI | no | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests tag mutation. |
| Call Attempt | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Christmas (AGENCY) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Client Replied --> Follow Up Due Date Changed | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| Closing Date Reminder - 2 days(WAITING) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| Cold Call Lead Form - Make Tags | UNKNOWN - inspect in GHL UI | no | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests tag mutation. |
| Cold Call Lead Form Submitted | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Cold Call Lead Submitted Automation | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Common Replies Workflow (NO SMS)(AGENCY) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| Completed Agreements Workflow | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Contact Tag-NO RESPONSE- MOVE TO "MIA" AND LOST | UNKNOWN - inspect in GHL UI | no | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests tag mutation. |
| Create New Opportunity | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Creative Offer Accepted Form | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Custom Date Reminder - 2 days(WAITING) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| Deal Blast (213 Banana Street) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Deal Closed in Dispositions >> Create Opportunity in Assets | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Deal Under Contract >> Create Opportunity in Disposition & TC | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Dialer Call Log | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| EMAIL- NEW INSTAGRAM AUTOMATION-10v.3 | UNKNOWN - inspect in GHL UI | no | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests tag mutation. |
| Enable DND on Texas Leads | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| FUP Custom Field -> Task | UNKNOWN - inspect in GHL UI | no | no | yes | no | no | no | keep | Auto-generated from workflow name only. Name suggests custom-field mutation. |
| Generate Dispo Cash Deal Description | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Generate Dispo Creative Deal Description | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Hot Buyer Alert | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Hot Seller Alert | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| IVR - All number | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Initial Onboarding Messages- AGENCY | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Instagram 2.9 V10 | UNKNOWN - inspect in GHL UI | no | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests tag mutation. |
| JV Agreement Workflow | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Jorge AI Bot - Inbound Message Handler | UNKNOWN - inspect in GHL UI | yes | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. |
| Jorge — Agent Notification | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Jorge — Bot Activation | UNKNOWN - inspect in GHL UI | no | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests tag mutation. |
| Jorge — Hot Buyer Alert | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Jorge — Hot Seller Alert | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Jorge — Manual Scheduling Fallback | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Jorge — Warm Buyer Nurture | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Jorge — Warm Seller Nurture | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| LYRIO-Foreclosure & Pre-foreclosure Workflows  \| powered by PRINTgenie | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| LYRIO-Probate and Pre-Probate Workflows \| powered by PRINTgenie | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| LYRIO-Want to Sell?? Campaign  \| powered by PRINTgenie | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| Lead Intake Notification | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Lead That Has NOT had any contact in 14 days | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Level - Initial Agent Outreach(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Level - Initial WS Buyer Outreach(AGENCY) | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| Level \| (Cold) Agent Nurture(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Level \| (Warm) Agent Nurture(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Level \| Closed Deal Asking For Referrals(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Lyrio - Mass Text Message | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| Lyrio - Mass Text Message - Probate (AGENCY) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| Lyrio- Tiktok Automation v.8.29(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Lyrio-Tiktok Follow up Workflow v.8.29(WAITING) | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| Make Agent Primary Contact Type(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Make PST | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Negative Conversation Added | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| New IE Realtors Workflow (AGENCY) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| New Inbound Lead | UNKNOWN - inspect in GHL UI | yes | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. |
| New Inbound Lead Workflow | UNKNOWN - inspect in GHL UI | yes | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. |
| New Lease Option Lead - Bandit Sign | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| New Workflow : 1768198593894 | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| New Workflow : 1772614693480 | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| New Workflow : 1772614906731 | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Open House Automation | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Open house F/U Automation | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Open house F/U Automationn | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| PHONE - INSTAGRAM V10.8 BEST | UNKNOWN - inspect in GHL UI | no | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests tag mutation. |
| PHONE - NEW INSTAGRAM AUTOMATION-10v.3 | UNKNOWN - inspect in GHL UI | no | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests tag mutation. |
| PHONE -Facebook V10.8 BEST | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Payment Fails AGENCY | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Payment succeeds AGENCY | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Phone recording | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Qualified Lead Notify - Email | UNKNOWN - inspect in GHL UI | no | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests tag mutation. |
| Qualified Lead Notify - SMS | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Quick Text Blast to Buyers (Template) | UNKNOWN - inspect in GHL UI | yes | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. |
| Remove From Workflow-(Removes from all active workflows and then removes tag)(AGENCY) | UNKNOWN - inspect in GHL UI | no | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests tag mutation. |
| Retail Buyer Disposition Changed | UNKNOWN - inspect in GHL UI | no | no | no | yes | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests pipeline/opportunity mutation. |
| Retail Buyer Personalized Campaign Organizer | UNKNOWN - inspect in GHL UI | yes | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. |
| SMS Sending Error | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| STG -  Closed Escrow (1 Year infinite Loop) | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| STG - Connected With Lender (10 Days) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| STG - Waiting On Pre-Approval (30 days) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| STG – 1 Year F-U | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| STG – 6 Month F-U | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| STG – Buyer Activation Sequence | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| STG – Buyer Activation Sequence (Data Driven + Driver) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| STG – Buyer Activation Sequence (Data Driven + Friendly) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| STG – Buyer Activation Sequence (Data Driven + Talkative) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| STG – Buyer Activation Sequence (Friendly + Driver) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| STG – Buyer Activation Sequence (Talkative + Driver) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| STG – Buyer Activation Sequence (Talkative + Friendly) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| STG – Buyer MIA (2 Months) | UNKNOWN - inspect in GHL UI | no | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests tag mutation. |
| STG – Buyer Paused (6 Months) | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| STG – Not Interested Buyer (Every 4 Months) | UNKNOWN - inspect in GHL UI | no | no | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. |
| STG – Not Qualified Buyer (6 Months) | UNKNOWN - inspect in GHL UI | no | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests tag mutation. |
| STG – Qualified Buyer (6 Days) | UNKNOWN - inspect in GHL UI | no | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests tag mutation. |
| Seller Dispo + Assign User | UNKNOWN - inspect in GHL UI | no | no | no | yes | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests pipeline/opportunity mutation. |
| Send Assignment Agreement Offer(AGENCY) | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Send Cash/Novation Contract Offer | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Sent Agreements Workflow | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Signal Sniping - "Niche Auction" | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Signal Sniping - "Niche Code Violations" | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Signal Sniping - "Niche Divorce" | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Signal Sniping - "Niche Expired Listings" | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Signal Sniping - "Niche HOA Lien" | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Signal Sniping - "Niche Inheritance" | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Signal Sniping - "Niche Lis Pendens" | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Signal Sniping - "Niche PFC/Foreclosure" | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Signal Sniping - "Niche Probate" | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Signal Sniping Email Opened v2 | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Signal Sniping SMS Error ??? | UNKNOWN - inspect in GHL UI | yes | no | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. |
| Single Line Dialer structure | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Social Media Form Automation | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Start Level  Initial Outreach(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Start Level Outreach(AGENCY) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Status - "Escrow Closed/Referral" Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. Name suggests pipeline/opportunity mutation. |
| Status - "Listed with Agent" Personalized (Data Driven + Driver) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Listed with Agent" Personalized (Data Driven + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Listed with Agent" Personalized (Driver + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Listed with Agent" Personalized (Driver + Talkative) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Listed with Agent" Personalized (Talkative + Data Driven) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Listed with Agent" Personalized (Talkative + Friendlyy) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Niche Data" SMS Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Offer Declined" Personalized (Data Driven + Driver) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Offer Declined" Personalized (Data Driven + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Offer Declined" Personalized (Driver + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Offer Declined" Personalized (Driver + Talkative) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Offer Declined" Personalized (Talkative + Data Driven) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Offer Declined" Personalized (Talkative + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Signed Elsewhere" Personalized (Data Driven + Driver) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Signed Elsewhere" Personalized (Data Driven + Talkative) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Signed Elsewhere" Personalized (Data Driven +Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Signed Elsewhere" Personalized (Driver + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Signed Elsewhere" Personalized (Driver + Talkative) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Signed Elsewhere" Personalized (Talkative + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Waiting for Photos" Personalized (Data Driven + Driver) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Waiting for Photos" Personalized (Data Driven + Talkative) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Waiting for Photos" Personalized (Driver + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Waiting for Photos" Personalized (Driver + Talkative) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Waiting for Photos" Personalized (Talkative + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Warm Lead" Personalized (Data Driven + Driver) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Warm Lead" Personalized (Data Driven + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Warm Lead" Personalized (Driver + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Warm Lead" Personalized (Talkative + Data Driven) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Warm Lead" Personalized (Talkative + Driver) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - "Warm Lead" Personalized (Talkative + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - Listed with Agent Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - Offer Declined Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - Offer Declined Campaign - 2.0 | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - Seller Activation Sequence Personalized (Data Driven + Driver) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - Seller Activation Sequence Personalized (Data Driven + Friendly) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - Seller Activation Sequence Personalized (Data Driven + Talkative) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - Seller Activation Sequence Personalized (Driver + Friendly) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - Seller Activation Sequence Personalized (Talkative + Friendly) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - Seller area Assigned Owner | UNKNOWN - inspect in GHL UI | no | yes | no | yes | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests tag mutation. Name suggests pipeline/opportunity mutation. |
| Status - Signed Elsewhere Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - Waiting for Photos Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status - Warm lead Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status -MIA Personal Campaign (Data Driven + Friendly) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status -SELLE Personalized Campaign Organizer | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status MIA Personal Campaign (Data Driven + Talkative) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status MIA Personal Campaign (Driver + Data Driven) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status MIA Personal Campaign (Driver + Talkative) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status MIA Personal Campaign (Friendly + Driver) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status MIA Personal Campaign (Friendly + Talkative) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status – Inbound Seller Lead (Email) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status – MIA-Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status – Seller Activation Sequence | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status- "Waiting for Photos" Personalized (Data Driven + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status- Escrow Closed/Referral (Data driven + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. Name suggests pipeline/opportunity mutation. |
| Status- Escrow Closed/Referral (Driver + Data Driven) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. Name suggests pipeline/opportunity mutation. |
| Status- Escrow Closed/Referral (Driver + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. Name suggests pipeline/opportunity mutation. |
| Status- Escrow Closed/Referral (Driver + Talkative) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. Name suggests pipeline/opportunity mutation. |
| Status- Escrow Closed/Referral (Talkative +  Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. Name suggests pipeline/opportunity mutation. |
| Status- Future Follow-Up Workflow | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status- Future Follow-Up( Friendly + Talkative) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status- Future Follow-Up(Data Driven + Driver) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status- Future Follow-Up(Data Driven + Friendly) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status- Future Follow-Up(Data Driven + Talkative) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status- Future Follow-Up(Friendly + Driver) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status- Future Follow-Up(Talkative + Driver) Campaign | UNKNOWN - inspect in GHL UI | yes | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Status- Seller Activation Sequence Personalized (Driver + Talkative) | UNKNOWN - inspect in GHL UI | yes | yes | no | no | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests message sending or campaign behavior. Name suggests tag mutation. |
| Tag Added Template (AGNECY) | UNKNOWN - inspect in GHL UI | no | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests tag mutation. |
| Tag When Primary Contact Type Added | UNKNOWN - inspect in GHL UI | no | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests tag mutation. |
| Tagging VIP Clients | UNKNOWN - inspect in GHL UI | no | yes | no | no | no | no | keep | Auto-generated from workflow name only. Name suggests tag mutation. |
| TiktTok dm ready?(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Tiktok Automation(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Track Opportunity | UNKNOWN - inspect in GHL UI | no | no | no | yes | no | no | keep | Auto-generated from workflow name only. Name suggests pipeline/opportunity mutation. |
| Update zillow link when contact/address added | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| Wholesale Seller Pipeline (Send Contract-Update Opp-Assign Tasks) | UNKNOWN - inspect in GHL UI | no | no | no | yes | yes | yes | rewrite | Auto-generated from workflow name only. Name suggests routing or bot-selection behavior. Name suggests pipeline/opportunity mutation. |
| Wholesaler \| Nurturing asking for more deals(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
| YourDailyHomes(WAITING) | UNKNOWN - inspect in GHL UI | no | no | no | no | no | no | keep | Auto-generated from workflow name only. |
