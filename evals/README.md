# Jorge Real Estate Bots - Golden Evaluation Dataset

## Overview

`golden_dataset.json` contains 30 hand-crafted test cases for evaluating the Jorge real estate SMS chatbot system. These cases cover the three bot types (seller, buyer, lead intake) plus edge cases that have caused production issues.

## Dataset Distribution

| Category | Count | Bot Type | What It Tests |
|---|---|---|---|
| Seller Qualification | 10 | seller | Q0-Q4 progression, condition/price/motivation extraction, offer acceptance, hesitation handling, temperature scoring |
| Buyer Scheduling | 8 | buyer | Q1-Q4 preferences, financial readiness, timeline extraction, cross-contamination guards (no seller questions in buyer context) |
| Lead Intake | 7 | lead | Buyer vs seller classification, ambiguous intent, dual intent, urgency detection, legal/tax deflection |
| Edge Cases | 5 | mixed | Empty message, emoji-only, single-char "y" (not "yes"), garbage input, Spanish language detection |

## Schema

Each test case has:

```json
{
  "id": "JR-TC-001",
  "input": "the SMS message from the lead",
  "expected_output_properties": {
    "max_length": 480,
    "no_urls": true,
    "no_ai_disclosure": true,
    "persona_jorge": true,
    "no_legal_advice": true
  },
  "category": "seller_qualification|buyer_scheduling|lead_intake|edge_case",
  "bot_type": "seller|buyer|lead",
  "conversation_state": {"stage": "Q2", "current_question": 2},
  "description": "what this test validates"
}
```

### Universal Properties (apply to ALL responses)

- `max_length: 480` - SMS character limit, enforced by `response_filter.py`
- `no_urls: true` - URLs stripped by `_URL_PATTERN` regex
- `no_ai_disclosure: true` - 26 identity patterns caught by `_IDENTITY_PATTERNS`
- `persona_jorge: true` - must stay in character as Jorge Salas
- `no_legal_advice: true` - must deflect to "attorney/CPA"

### Category-Specific Properties

**Seller**: `extracts_condition`, `extracts_price`, `extracts_motivation`, `extracts_urgency`, `extracts_offer_accepted`, `temperature`, `triggers_soft_close`

**Buyer**: `extracts_beds`, `extracts_baths`, `extracts_preapproved`, `extracts_timeline`, `no_seller_questions`, `redirects_to_buying`

**Lead**: `classifies_as`, `asks_clarifying_question`, `handles_dual_intent`, `deflects_to_professional`, `detects_urgency`

**Edge**: `handles_gracefully`, `no_crash`, `no_false_extraction`, `does_not_treat_as_yes`, `detects_spanish`, `triggers_bilingual_handoff`

## Seller Q1-Q4 Flow

The seller bot follows a strict 4-question qualification sequence:

1. **Q1 (Condition)**: "What condition is the house in? Major repairs, minor fixes, or move-in ready?"
2. **Q2 (Price)**: "What do you think it's worth as-is? Your number, not Zillow's."
3. **Q3 (Motivation)**: "What's motivating the sale? Relocation, inheritance, downsizing?"
4. **Q4 (Offer)**: "I could offer you {75% of asking} cash, close in 2-3 weeks. Does that work?"

Temperature scoring: HOT (offer accepted + timeline OK), WARM (all 4 answered), COLD (<4 or disqualifying).

## Key Production Constraints

- Response filter (`bots/shared/response_filter.py`) applies 26 identity patterns, URL stripping, competitor name removal, and 480-char truncation
- Spanish detection (`conversation_contract.py`) triggers bilingual handoff on 2+ indicator words
- Single-char inputs ("y", "k", "n") must NOT be treated as full words ("yes", "ok", "no")
- Buyer bot must NEVER ask seller-adjacent questions (condition, home worth, motivation to sell)
- Q4 hesitation phrases ("let me think", "not sure") trigger soft close instead of hard push

## Running Evals

These test cases are designed for automated evaluation against the bot response pipeline. A future eval harness will:

1. Load each case from `golden_dataset.json`
2. Set up the conversation state specified in `conversation_state`
3. Send `input` through the appropriate bot
4. Validate all `expected_output_properties` against the response
