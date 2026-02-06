# Jorge's Seller Bot - Quick Start Guide

Complete guide for using Jorge's Q1-Q4 Seller Qualification Bot in production.

---

## Installation

### 1. Install Dependencies
```bash
cd jorge_real_estate_bots
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add:
ANTHROPIC_API_KEY=your_claude_api_key
GHL_ACCESS_TOKEN=your_ghl_access_token
GHL_LOCATION_ID=your_location_id
```

### 3. Verify Installation
```bash
# Run tests
python -m pytest tests/test_jorge_seller_bot.py -v

# Expected output:
# ============================== 28 passed in 1.49s ==============================
```

---

## Basic Usage

### Import and Initialize
```python
from bots.seller_bot import create_seller_bot

# Create seller bot with default GHL client
seller_bot = create_seller_bot()

# Or provide custom GHL client
from bots.shared.ghl_client import GHLClient

ghl_client = GHLClient(access_token="your_token")
seller_bot = create_seller_bot(ghl_client=ghl_client)
```

### Process Seller Messages
```python
# Process a seller inquiry
result = await seller_bot.process_seller_message(
    contact_id="ghl_contact_12345",
    location_id="ghl_location_001",
    message="I want to sell my house",
    contact_info={"name": "John Smith", "phone": "214-555-1234"}
)

# Access results
print(f"Jorge's Response: {result.response_message}")
print(f"Temperature: {result.seller_temperature}")  # "hot", "warm", or "cold"
print(f"Questions Answered: {result.questions_answered}/4")
print(f"Qualified: {result.qualification_complete}")
print(f"Next Steps: {result.next_steps}")
```

---

## Q1-Q4 Qualification Flow

### Q0: Initial Contact
**Seller**: "I want to sell my house"

**Jorge**: "Look, I'm not here to waste time. What condition is the house in? Be honest..."

### Q1: Property Condition
**Seller**: "It needs major repairs, new roof and HVAC"

**System extracts**:
- `condition: "needs_major_repairs"`

**Jorge**: "What do you REALISTICALLY think it's worth as-is? Don't tell me what Zillow says..."

### Q2: Price Expectation
**Seller**: "Maybe $350,000"

**System extracts**:
- `price_expectation: 350000`
- Validates against $200K-$800K range

**Jorge**: "What's your real motivation? Job, financial problems, inherited property..."

### Q3: Motivation to Sell
**Seller**: "I got a job transfer to Austin, need to move in 6 weeks"

**System extracts**:
- `motivation: "job_relocation"`
- `urgency: "high"`

**Jorge**: "If I offer you $262,500 cash and close in 2-3 weeks, would you take it?"

### Q4: Offer Acceptance
**Seller**: "Yes, that works for me"

**System extracts**:
- `offer_accepted: True`
- `timeline_acceptable: True`

**Result**: HOT lead → CMA automation triggered!

---

## Temperature Scoring

### HOT Lead (Immediate Handoff)
```python
# Criteria
questions_answered == 4
offer_accepted == True
timeline_acceptable == True

# Actions
- Add tag: "seller_hot"
- Trigger CMA workflow
- Schedule consultation
```

### WARM Lead (Nurturing)
```python
# Criteria
questions_answered == 4
price in $200K-$800K range
motivation provided

# Actions
- Add tag: "seller_warm"
- Start follow-up sequence
```

### COLD Lead (More Qualification)
```python
# Criteria
questions_answered < 4
OR price out of range
OR disqualifying responses

# Actions
- Add tag: "seller_cold"
- Continue qualification
```

---

## GHL Integration

### Tags Applied
```python
# Automatically applied based on temperature
result.actions_taken = [
    {"type": "add_tag", "tag": "seller_hot"},
    # or "seller_warm", "seller_cold"
]
```

### Custom Fields Updated
```python
# All custom fields updated automatically
{
    "seller_temperature": "hot",
    "seller_questions_answered": "4",
    "property_condition": "needs_major_repairs",
    "seller_price_expectation": "350000",
    "seller_motivation": "job_relocation"
}
```

### Workflows Triggered
```python
# CMA automation for HOT leads
{
    "type": "trigger_workflow",
    "workflow_id": "cma_automation",
    "workflow_name": "CMA Report Generation"
}
```

---

## Analytics and Reporting

### Get Seller Analytics
```python
analytics = await seller_bot.get_seller_analytics(
    contact_id="seller_12345",
    location_id="loc_001"
)

# Returns
{
    "seller_temperature": "hot",
    "questions_answered": 4,
    "qualification_progress": "4/4",
    "qualification_complete": True,
    "property_condition": "needs_major_repairs",
    "price_expectation": 350000,
    "motivation": "job_relocation",
    "urgency": "high",
    "offer_accepted": True,
    "timeline_acceptable": True,
    "last_interaction": "2026-01-23T10:30:00"
}
```

---

## FastAPI Integration

### Add Seller Bot Endpoint
```python
from fastapi import FastAPI, HTTPException
from bots.seller_bot import create_seller_bot
from pydantic import BaseModel

app = FastAPI()
seller_bot = create_seller_bot()

class SellerMessage(BaseModel):
    contact_id: str
    location_id: str
    message: str
    contact_info: dict = {}

@app.post("/seller/message")
async def process_seller(data: SellerMessage):
    try:
        result = await seller_bot.process_seller_message(
            contact_id=data.contact_id,
            location_id=data.location_id,
            message=data.message,
            contact_info=data.contact_info
        )

        return {
            "response": result.response_message,
            "temperature": result.seller_temperature,
            "questions_answered": result.questions_answered,
            "qualified": result.qualification_complete,
            "next_steps": result.next_steps,
            "actions": result.actions_taken
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Test Endpoint
```bash
curl -X POST http://localhost:8000/seller/message \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": "test_seller_001",
    "location_id": "loc_001",
    "message": "I want to sell my house",
    "contact_info": {"name": "John Smith"}
  }'
```

---

## GHL Webhook Integration

### Setup Webhook Handler
```python
@app.post("/webhooks/ghl/seller-inbound")
async def ghl_seller_webhook(request: Request):
    """Handle incoming seller messages from GHL"""

    # Parse GHL webhook payload
    payload = await request.json()

    contact_id = payload.get("contactId")
    location_id = payload.get("locationId")
    message = payload.get("message", {}).get("body", "")

    # Process with seller bot
    result = await seller_bot.process_seller_message(
        contact_id=contact_id,
        location_id=location_id,
        message=message
    )

    # Send response back via GHL
    await ghl_client.send_message(
        contact_id=contact_id,
        message=result.response_message
    )

    return {"status": "success", "temperature": result.seller_temperature}
```

### Configure in GHL
1. Go to Settings → Integrations → Webhooks
2. Create new webhook for "Inbound Message"
3. Set URL: `https://your-domain.com/webhooks/ghl/seller-inbound`
4. Select events: "SMS Received", "WhatsApp Received"
5. Save and test

---

## Jorge's Phrases (Confrontational Tone)

The bot randomly selects from Jorge's authentic phrases:

```python
jorge_phrases = [
    "Look, I'm not here to waste time",
    "Let me be straight with you",
    "I buy houses fast, but only if you're serious",
    "Don't give me the runaround",
    "Are you actually ready to sell, or just shopping around?",
    "I need the truth, not some sugar-coated BS",
    "If you're not serious, don't waste my time",
    "Here's the deal - no games, no nonsense"
]
```

These are automatically inserted at the start of Q1 to set the tone.

---

## Advanced Features

### Concurrent Conversations
```python
# Seller bot handles multiple sellers simultaneously
results = await asyncio.gather(
    seller_bot.process_seller_message("seller_A", "loc_001", "I want to sell"),
    seller_bot.process_seller_message("seller_B", "loc_001", "Need cash fast"),
    seller_bot.process_seller_message("seller_C", "loc_001", "What's my house worth?")
)

# Each conversation maintains independent state
```

### Custom Offer Calculation
```python
# Default: 75% of price expectation
# Seller says: "$400,000"
# Jorge offers: $300,000 (75% * $400K)

# Customize offer percentage
class CustomSellerBot(JorgeSellerBot):
    def _calculate_offer(self, price_expectation: int) -> int:
        return int(price_expectation * 0.70)  # 70% instead of 75%
```

### State Persistence
```python
# Save state to database (example)
import json

# Get state
state = seller_bot._states.get("seller_12345")

# Serialize
state_json = json.dumps({
    "current_question": state.current_question,
    "questions_answered": state.questions_answered,
    "condition": state.condition,
    "price_expectation": state.price_expectation,
    "motivation": state.motivation,
    "offer_accepted": state.offer_accepted
})

# Save to DB
await db.save_seller_state("seller_12345", state_json)

# Restore state
state_data = json.loads(await db.get_seller_state("seller_12345"))
seller_bot._states["seller_12345"] = SellerQualificationState(**state_data)
```

---

## Error Handling

### Graceful Fallbacks
```python
# If Claude AI fails, bot returns fallback response
result = await seller_bot.process_seller_message(...)

# Fallback response structure
if "error" in result.analytics:
    print("Error occurred, using fallback response")
    print(result.response_message)  # "Thanks for your interest..."
```

### Custom Error Handling
```python
try:
    result = await seller_bot.process_seller_message(...)
except Exception as e:
    logger.error(f"Seller bot error: {e}")
    # Send notification to admin
    await notify_admin(f"Seller bot error for {contact_id}: {e}")
    # Send fallback to seller
    await send_fallback_message(contact_id)
```

---

## Monitoring and Metrics

### Track Key Metrics
```python
# Qualification funnel
total_sellers = len(seller_bot._states)
q1_reached = sum(1 for s in seller_bot._states.values() if s.current_question >= 1)
q4_reached = sum(1 for s in seller_bot._states.values() if s.current_question >= 4)
hot_leads = sum(1 for s in seller_bot._states.values()
                if s.offer_accepted and s.timeline_acceptable)

# Conversion rates
q1_to_q4_rate = q4_reached / q1_reached if q1_reached > 0 else 0
q4_to_hot_rate = hot_leads / q4_reached if q4_reached > 0 else 0

print(f"Qualification Funnel:")
print(f"Q1 Reached: {q1_reached}/{total_sellers} ({q1_reached/total_sellers*100:.1f}%)")
print(f"Q4 Reached: {q4_reached}/{total_sellers} ({q4_reached/total_sellers*100:.1f}%)")
print(f"HOT Leads: {hot_leads}/{total_sellers} ({hot_leads/total_sellers*100:.1f}%)")
```

---

## Troubleshooting

### Issue: Bot not responding
**Check**:
1. Anthropic API key is valid
2. GHL access token is valid
3. Network connectivity
4. Check logs for errors

### Issue: Wrong temperature assigned
**Check**:
1. All 4 questions answered?
2. Offer accepted and timeline OK for HOT?
3. Price expectation in $200K-$800K range?

### Issue: CMA not triggering
**Check**:
1. Lead temperature is "hot"
2. GHL workflow ID is correct
3. Workflow is active in GHL
4. Check seller_bot._generate_actions() logs

---

## Testing

### Run Full Test Suite
```bash
# All seller bot tests
python -m pytest tests/test_jorge_seller_bot.py -v

# With coverage
python -m pytest tests/test_jorge_seller_bot.py --cov=bots.seller_bot --cov-report=html

# Specific test
python -m pytest tests/test_jorge_seller_bot.py::TestJorgeSellerBot::test_q4_offer_accepted -v
```

### Manual Testing Script
```python
import asyncio
from bots.seller_bot import create_seller_bot

async def test_full_qualification():
    seller_bot = create_seller_bot()
    contact_id = "test_seller_manual"
    location_id = "test_loc"

    # Q0 → Q1
    r1 = await seller_bot.process_seller_message(
        contact_id, location_id, "I want to sell my house"
    )
    print(f"Q1: {r1.response_message}\n")

    # Q1 → Q2
    r2 = await seller_bot.process_seller_message(
        contact_id, location_id, "It needs major repairs"
    )
    print(f"Q2: {r2.response_message}\n")

    # Q2 → Q3
    r3 = await seller_bot.process_seller_message(
        contact_id, location_id, "I think $350,000"
    )
    print(f"Q3: {r3.response_message}\n")

    # Q3 → Q4
    r4 = await seller_bot.process_seller_message(
        contact_id, location_id, "Job transfer to Austin"
    )
    print(f"Q4: {r4.response_message}\n")

    # Q4 → Result
    r5 = await seller_bot.process_seller_message(
        contact_id, location_id, "Yes, let's do it"
    )
    print(f"Final: {r5.response_message}")
    print(f"Temperature: {r5.seller_temperature}")
    print(f"Qualified: {r5.qualification_complete}")

asyncio.run(test_full_qualification())
```

---

## Production Deployment

### 1. Environment Setup
```bash
# Production .env
ANTHROPIC_API_KEY=sk-ant-prod-xxxxx
GHL_ACCESS_TOKEN=ghl-prod-xxxxx
GHL_LOCATION_ID=prod-location-id
LOG_LEVEL=INFO
SENTRY_DSN=https://sentry.io/xxxxx  # Optional monitoring
```

### 2. Deploy with Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "bots.lead_bot.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3. Monitor Performance
```python
# Add to seller_bot.py
import time

async def process_seller_message(self, ...):
    start_time = time.time()

    result = ...  # processing

    elapsed = time.time() - start_time
    logger.info(f"Seller message processed in {elapsed:.2f}s")

    # Alert if too slow
    if elapsed > 2.0:
        logger.warning(f"Slow processing: {elapsed:.2f}s for {contact_id}")
```

---

## Support

### Documentation
- Full integration report: `PHASE2_SELLER_BOT_INTEGRATION.md`
- API documentation: `docs/API_DOCUMENTATION.md`
- Phase 1 completion: `PHASE1_COMPLETION_REPORT.md`

### Contact
- Email: support@jorge-ai.com (example)
- Slack: #seller-bot-support (example)

---

**Last Updated**: January 23, 2026
**Version**: 1.0.0
**Author**: Claude Code Assistant
