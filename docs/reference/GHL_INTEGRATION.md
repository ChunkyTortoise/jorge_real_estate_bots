# GoHighLevel Integration Guide

**Complete setup guide for Jorge's Real Estate AI Bots with GHL**

## 🎯 Integration Overview

Jorge's bots integrate with GoHighLevel via:
- **Webhooks**: Real-time lead/contact notifications
- **API Calls**: Update contact data, create tasks, move pipeline stages
- **Custom Fields**: Store AI analysis results in GHL
- **Workflows**: Trigger automated sequences based on bot intelligence

## 📋 Prerequisites

### Required GHL Plan
- **Minimum**: Agency Starter ($297/month)
- **Recommended**: Agency Pro ($497/month) for full webhook support
- **Required Permissions**: API access, webhook management, custom fields

### Required API Access
```
Settings → Integrations → API → Create App
- App Name: "Jorge Real Estate Bots"
- Redirect URI: https://jorge-bots.com/oauth/callback
- Scopes: contacts.write, workflows.write, calendars.write
```

## 🔧 Step 1: Custom Fields Setup

### Lead Bot Custom Fields
Navigate to: `Settings → Custom Fields → Contact Fields`

```json
// Create these custom fields for contacts
{
    "ai_lead_score": {
        "type": "Number",
        "label": "AI Lead Score (0-100)",
        "required": false,
        "default": 0
    },
    "lead_temperature": {
        "type": "Dropdown",
        "label": "Lead Temperature",
        "options": ["hot", "warm", "cold"],
        "required": false,
        "default": "cold"
    },
    "ai_analysis_date": {
        "type": "Date",
        "label": "Last AI Analysis",
        "required": false
    },
    "budget_qualified": {
        "type": "Checkbox",
        "label": "Budget Qualified",
        "required": false,
        "default": false
    },
    "financing_status": {
        "type": "Dropdown",
        "label": "Financing Status",
        "options": ["preapproved", "exploring", "not_started", "cash"],
        "required": false
    },
    "timeline_urgency": {
        "type": "Dropdown",
        "label": "Timeline",
        "options": ["ASAP", "30_days", "60_days", "90_days", "180_days", "exploring"],
        "required": false
    },
    "property_type_interest": {
        "type": "Dropdown",
        "label": "Property Type Interest",
        "options": ["residential", "commercial", "investment", "land"],
        "required": false,
        "default": "residential"
    }
}
```

### Seller Bot Custom Fields
```json
{
    "estimated_property_value": {
        "type": "Number",
        "label": "AI Estimated Value",
        "required": false,
        "default": 0
    },
    "cma_generated": {
        "type": "Checkbox",
        "label": "CMA Generated",
        "required": false,
        "default": false
    },
    "cma_pdf_url": {
        "type": "Text",
        "label": "CMA Report URL",
        "required": false
    },
    "pricing_confidence": {
        "type": "Number",
        "label": "Pricing Confidence %",
        "required": false,
        "default": 0
    },
    "market_position": {
        "type": "Dropdown",
        "label": "Market Position",
        "options": ["below_market", "at_market", "above_market"],
        "required": false
    },
    "recommended_list_price": {
        "type": "Number",
        "label": "AI Recommended List Price",
        "required": false,
        "default": 0
    }
}
```

### Buyer Bot Custom Fields
```json
{
    "buyer_score": {
        "type": "Number",
        "label": "Buyer Score (0-100)",
        "required": false,
        "default": 0
    },
    "properties_matched": {
        "type": "Number",
        "label": "Properties Matched",
        "required": false,
        "default": 0
    },
    "last_property_viewed": {
        "type": "Text",
        "label": "Last Property Viewed",
        "required": false
    },
    "showing_preferences": {
        "type": "Text Area",
        "label": "Showing Preferences",
        "required": false
    },
    "match_criteria_learned": {
        "type": "Text Area",
        "label": "AI Learned Preferences",
        "required": false
    }
}
```

## 🔔 Step 2: Webhook Configuration

### Navigate to Webhooks
`Settings → Integrations → Webhooks → Create Webhook`

### Lead Bot Webhooks

#### 1. New Lead Webhook
```json
{
    "name": "Jorge Bots - New Lead",
    "url": "https://api.jorge-bots.com/lead_bot/ghl/webhook/new-lead",
    "method": "POST",
    "events": ["ContactCreate"],
    "version": "v2",
    "headers": {
        "Authorization": "Bearer YOUR_WEBHOOK_SECRET",
        "Content-Type": "application/json"
    }
}
```

#### 2. Lead Response Webhook
```json
{
    "name": "Jorge Bots - Lead Response",
    "url": "https://api.jorge-bots.com/lead_bot/ghl/webhook/lead-response",
    "method": "POST",
    "events": ["ConversationMessageCreate"],
    "version": "v2",
    "headers": {
        "Authorization": "Bearer YOUR_WEBHOOK_SECRET",
        "Content-Type": "application/json"
    }
}
```

### Seller Bot Webhooks

#### 3. Seller Inquiry Webhook
```json
{
    "name": "Jorge Bots - Seller Inquiry",
    "url": "https://api.jorge-bots.com/seller_bot/ghl/webhook/new-seller",
    "method": "POST",
    "events": ["ContactCreate"],
    "filters": {
        "tags": ["seller", "listing_inquiry", "sell_home"]
    },
    "version": "v2"
}
```

#### 4. Listing Created Webhook
```json
{
    "name": "Jorge Bots - Listing Created",
    "url": "https://api.jorge-bots.com/seller_bot/ghl/webhook/listing-created",
    "method": "POST",
    "events": ["OpportunityCreate"],
    "filters": {
        "pipeline_id": "YOUR_LISTING_PIPELINE_ID"
    },
    "version": "v2"
}
```

### Buyer Bot Webhooks

#### 5. Buyer Inquiry Webhook
```json
{
    "name": "Jorge Bots - Buyer Inquiry",
    "url": "https://api.jorge-bots.com/buyer_bot/ghl/webhook/new-buyer",
    "method": "POST",
    "events": ["ContactCreate"],
    "filters": {
        "tags": ["buyer", "home_buyer", "looking_to_buy"]
    },
    "version": "v2"
}
```

## 🔄 Step 3: Pipeline Configuration

### Lead Pipeline Setup
Navigate to: `CRM → Pipelines → Create Pipeline`

```json
{
    "name": "Jorge Lead Pipeline",
    "stages": [
        {
            "name": "New Lead",
            "id": "new_lead",
            "position": 1,
            "automation": "webhook_to_lead_bot"
        },
        {
            "name": "AI Qualified - Hot",
            "id": "hot_lead",
            "position": 2,
            "automation": "immediate_call_task"
        },
        {
            "name": "AI Qualified - Warm",
            "id": "warm_lead",
            "position": 3,
            "automation": "24hr_followup_sequence"
        },
        {
            "name": "AI Qualified - Cold",
            "id": "cold_lead",
            "position": 4,
            "automation": "weekly_nurture_sequence"
        },
        {
            "name": "Appointment Scheduled",
            "id": "appointment_scheduled",
            "position": 5
        },
        {
            "name": "Under Contract",
            "id": "under_contract",
            "position": 6
        },
        {
            "name": "Closed",
            "id": "closed",
            "position": 7
        }
    ]
}
```

### Seller Pipeline Setup
```json
{
    "name": "Jorge Seller Pipeline",
    "stages": [
        {
            "name": "Seller Inquiry",
            "id": "seller_inquiry",
            "position": 1,
            "automation": "cma_generation_trigger"
        },
        {
            "name": "CMA Delivered",
            "id": "cma_delivered",
            "position": 2,
            "automation": "listing_appointment_sequence"
        },
        {
            "name": "Listing Appointment",
            "id": "listing_appointment",
            "position": 3
        },
        {
            "name": "Listed",
            "id": "listed",
            "position": 4,
            "automation": "marketing_campaign_trigger"
        },
        {
            "name": "Under Contract",
            "id": "seller_under_contract",
            "position": 5
        },
        {
            "name": "Sold",
            "id": "sold",
            "position": 6
        }
    ]
}
```

## ⚙️ Step 4: Workflow Automation

### Hot Lead Auto-Response Workflow

#### Trigger: Contact moved to "AI Qualified - Hot" stage
```json
{
    "name": "Hot Lead Immediate Response",
    "trigger": {
        "type": "Pipeline Stage Change",
        "pipeline": "Jorge Lead Pipeline",
        "stage": "AI Qualified - Hot"
    },
    "actions": [
        {
            "type": "Send SMS",
            "delay": "0 minutes",
            "message": "Hi {{contact.first_name}}, thanks for your interest! I'm Jorge, your local real estate expert. Quick question: are you looking to buy, sell, or explore options? I can help you get started today!"
        },
        {
            "type": "Create Task",
            "delay": "2 minutes",
            "task": {
                "title": "URGENT: Call Hot Lead {{contact.first_name}}",
                "description": "AI Score: {{contact.ai_lead_score}}. Lead Temperature: HOT. Must call within 5 minutes for 10x conversion rate.",
                "due_date": "+5 minutes",
                "assigned_to": "Jorge"
            }
        },
        {
            "type": "Send Email",
            "delay": "15 minutes",
            "template": "hot_lead_property_recommendations"
        }
    ]
}
```

### CMA Generation Workflow

#### Trigger: Seller inquiry with property address
```json
{
    "name": "Automatic CMA Generation",
    "trigger": {
        "type": "Contact Created",
        "filters": {
            "tags": ["seller"],
            "custom_fields": {
                "property_address": "not_empty"
            }
        }
    },
    "actions": [
        {
            "type": "HTTP Post",
            "delay": "0 minutes",
            "url": "https://api.jorge-bots.com/seller_bot/generate-cma",
            "payload": {
                "contact_id": "{{contact.id}}",
                "property_address": "{{contact.property_address}}"
            }
        },
        {
            "type": "Wait",
            "duration": "2 minutes"
        },
        {
            "type": "Send Email",
            "delay": "0 minutes",
            "message": "Hi {{contact.first_name}}, I've prepared a comprehensive market analysis for your property at {{contact.property_address}}. The AI-generated CMA shows an estimated value of ${{contact.estimated_property_value}}. Please find the detailed report attached. When would be a good time to discuss your selling strategy?",
            "attachments": ["{{contact.cma_pdf_url}}"]
        }
    ]
}
```

## 📊 Step 5: Dashboard Integration

### GHL Dashboard Widgets

#### Custom AI Metrics Widget
Add to Jorge's GHL dashboard:
```html
<!-- Custom HTML Widget -->
<div class="ai-metrics-widget">
    <h3>🤖 AI Bot Performance</h3>
    <div class="metrics-grid">
        <div class="metric">
            <span class="label">Hot Leads</span>
            <span class="value" id="hot-leads">{{hot_leads_count}}</span>
        </div>
        <div class="metric">
            <span class="label">Avg Response</span>
            <span class="value" id="response-time">{{avg_response_time}}</span>
        </div>
        <div class="metric">
            <span class="label">CMAs Today</span>
            <span class="value" id="cmas-generated">{{cmas_generated_today}}</span>
        </div>
    </div>
</div>

<script>
// Auto-refresh metrics every 30 seconds
setInterval(() => {
    fetch('https://api.jorge-bots.com/command_center/metrics/ghl-widget')
    .then(response => response.json())
    .then(data => {
        document.getElementById('hot-leads').textContent = data.hot_leads;
        document.getElementById('response-time').textContent = data.avg_response_time;
        document.getElementById('cmas-generated').textContent = data.cmas_generated;
    });
}, 30000);
</script>
```

## 🔐 Step 6: Security Setup

### API Key Management

#### 1. Generate GHL API Key
```
Settings → Integrations → API → Generate Key
- Name: "Jorge Bots API Access"
- Permissions: Read/Write Contacts, Read/Write Opportunities, Read/Write Tasks
```

#### 2. Webhook Signature Verification
```python
# Add this to your webhook handlers
import hmac
import hashlib

def verify_ghl_signature(payload, signature, secret):
    """Verify GHL webhook signature for security"""
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, f"sha256={expected}")

# Use in webhook endpoints
@app.post("/ghl/webhook/new-lead")
async def handle_new_lead(request: Request):
    signature = request.headers.get("X-GHL-Signature")
    payload = await request.body()

    if not verify_ghl_signature(payload, signature, GHL_WEBHOOK_SECRET):
        raise HTTPException(401, "Invalid signature")

    # Process webhook...
```

### IP Whitelisting (Optional)
Add Jorge's bot server IPs to GHL whitelist:
```
Settings → Security → IP Whitelist
- Add: Your DigitalOcean droplet IP
- Add: Any additional server IPs
```

## 📱 Step 7: Mobile App Integration

### GHL Mobile App Setup
Configure mobile notifications for Jorge:

```json
{
    "mobile_notifications": {
        "hot_leads": {
            "enabled": true,
            "sound": "urgent",
            "vibrate": true,
            "message": "🔥 Hot Lead Alert: {{contact.first_name}} needs immediate attention (Score: {{contact.ai_lead_score}})"
        },
        "cma_requests": {
            "enabled": true,
            "sound": "default",
            "message": "📊 CMA requested for {{contact.property_address}}"
        },
        "bot_errors": {
            "enabled": true,
            "sound": "alert",
            "message": "🚨 Bot Error: {{error_type}} needs attention"
        }
    }
}
```

## 🧪 Step 8: Testing & Validation

### Test Webhook Endpoints
```bash
# Test Lead Bot webhook
curl -X POST https://api.jorge-bots.com/lead_bot/ghl/webhook/new-lead \
  -H "Content-Type: application/json" \
  -H "X-GHL-Signature: sha256=test_signature" \
  -d '{
    "id": "test_contact_123",
    "name": "Test Lead",
    "email": "test@example.com",
    "source": "website"
  }'

# Expected: 200 OK with lead score response
```

### Validate Custom Fields
1. Create test contact in GHL
2. Verify AI custom fields appear in contact record
3. Test webhook triggers when contact created
4. Confirm custom fields updated by bot response

### Test Workflows
1. Create test lead with "hot" temperature
2. Verify immediate SMS sent
3. Confirm task created for Jorge
4. Check email sequence triggered

## 🚨 Troubleshooting

### Common Issues

#### Webhook Not Firing
```bash
# Check webhook logs in GHL
Settings → Integrations → Webhooks → View Logs

# Common solutions:
1. Verify webhook URL is accessible (not localhost)
2. Check webhook secret matches bot configuration
3. Ensure events are properly selected
4. Verify contact meets filter criteria (tags, custom fields)
```

#### Custom Fields Not Updating
```python
# Verify field names match exactly (case sensitive)
# Check API permissions include contacts.write
# Confirm contact ID exists in GHL

# Debug API call
response = requests.patch(
    f"https://services.leadconnectorhq.com/contacts/{contact_id}",
    headers={"Authorization": f"Bearer {ghl_api_key}"},
    json={"customField": {"ai_lead_score": 85}}
)
print(response.status_code, response.json())
```

#### Rate Limiting Issues
```python
# Implement retry logic with exponential backoff
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def ghl_api_call(endpoint, data):
    # API call implementation
    pass
```

## 📞 Support Contacts

### GHL Support
- **Documentation**: https://help.gohighlevel.com
- **API Docs**: https://marketplace.gohighlevel.com/docs
- **Support**: help@gohighlevel.com

### Jorge Bot Support
- **Technical Issues**: jorge-bots-support@example.com
- **Integration Help**: Available during setup phase
- **Emergency**: Critical issues affecting lead response times

---

**This integration guide ensures Jorge's bots work seamlessly with GoHighLevel to achieve the 5-minute response time requirement for maximum lead conversion rates.**