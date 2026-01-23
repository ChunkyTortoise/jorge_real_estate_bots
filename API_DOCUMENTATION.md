# API Documentation - Jorge's Real Estate Bots

## 🚀 Base URLs

- **Lead Bot**: `http://localhost:8001` (Production: `https://api.jorge-bots.com/lead`)
- **Seller Bot**: `http://localhost:8002` (Production: `https://api.jorge-bots.com/seller`)
- **Buyer Bot**: `http://localhost:8003` (Production: `https://api.jorge-bots.com/buyer`)
- **Command Center**: `http://localhost:8501` (Production: `https://dashboard.jorge-bots.com`)

## 🔥 Lead Bot API

### POST `/ghl/webhook/new-lead`
**Purpose**: Handle new lead from GHL
**Trigger**: GHL contact.created webhook
**Performance**: Must complete in <5 minutes for 10x conversion

**Request Body:**
```json
{
    "id": "contact_id_12345",
    "name": "John Smith",
    "email": "john@example.com",
    "phone": "+1234567890",
    "source": "facebook_ads",
    "message": "Interested in buying a home",
    "custom_fields": {
        "budget": "400000",
        "timeline": "60_days"
    }
}
```

**Response:**
```json
{
    "status": "processed",
    "score": 87,
    "temperature": "hot",
    "follow_up_scheduled": true,
    "processing_time_ms": 450,
    "next_action": {
        "type": "immediate_call",
        "scheduled_for": "2024-01-23T15:05:00Z"
    }
}
```

### POST `/ghl/webhook/lead-response`
**Purpose**: Handle lead response to outreach
**Trigger**: GHL conversation.message.added webhook

**Request Body:**
```json
{
    "lead_id": "contact_id_12345",
    "message": "Yes, I'm still interested. Can we schedule a showing?",
    "channel": "sms",
    "timestamp": "2024-01-23T15:30:00Z",
    "conversation_history": [...]
}
```

**Response:**
```json
{
    "status": "analyzed",
    "sentiment": "positive",
    "intent": "schedule_showing",
    "urgency": "high",
    "next_action": {
        "type": "schedule_showing",
        "priority": "immediate",
        "message_template": "Great! I can show you the property tomorrow. What time works best?"
    }
}
```

### GET `/dashboard/metrics`
**Purpose**: Get lead bot metrics for dashboard

**Response:**
```json
{
    "hot_leads": {"count": 23, "change": "+5"},
    "warm_leads": {"count": 45, "change": "-2"},
    "cold_leads": {"count": 78, "change": "+12"},
    "avg_response_time": "3.2 minutes",
    "conversion_rate": "32%",
    "daily_qualified": 8,
    "performance": {
        "api_response_time": "412ms",
        "qualification_accuracy": "89%",
        "uptime": "99.95%"
    }
}
```

## 💰 Seller Bot API

### POST `/ghl/webhook/new-seller`
**Purpose**: Handle new seller inquiry from GHL
**Trigger**: GHL contact.created with seller tags

**Request Body:**
```json
{
    "id": "contact_id_67890",
    "name": "Sarah Johnson",
    "email": "sarah@example.com",
    "phone": "+1987654321",
    "property_address": "123 Oak Street, Dallas, TX 75201",
    "property_type": "residential",
    "estimated_value": 550000,
    "motivation": "relocating_for_job",
    "timeline": "90_days"
}
```

**Response:**
```json
{
    "status": "analyzed",
    "cma_generated": true,
    "estimated_value": 565000,
    "confidence": 92,
    "market_position": "slightly_above_market",
    "cma_url": "https://jorge-bots.s3.com/cma/contact_67890_cma.pdf",
    "next_actions": [
        {"type": "send_cma", "scheduled_for": "immediate"},
        {"type": "schedule_listing_appointment", "scheduled_for": "+2_hours"}
    ]
}
```

### POST `/generate-cma`
**Purpose**: Generate CMA for specific property
**Performance**: Must complete in <90 seconds

**Request Body:**
```json
{
    "property_address": "123 Oak Street, Dallas, TX 75201",
    "contact_id": "contact_67890",
    "property_details": {
        "bedrooms": 4,
        "bathrooms": 3,
        "sqft": 2400,
        "lot_size": 0.25,
        "year_built": 2010
    }
}
```

**Response:**
```json
{
    "estimated_value": 565000,
    "value_range": [540000, 590000],
    "confidence": 92,
    "comparable_sales": [
        {
            "address": "125 Oak Street",
            "sale_price": 570000,
            "sale_date": "2024-01-15",
            "days_on_market": 18,
            "sqft": 2380
        }
    ],
    "market_analysis": {
        "trend": "+2.3% (6 months)",
        "inventory": "low",
        "dom_average": 28
    },
    "pricing_recommendations": {
        "conservative": 540000,
        "market": 565000,
        "aggressive": 580000
    },
    "pdf_report": {
        "url": "https://jorge-bots.s3.com/cma/cma_123_oak_st.pdf",
        "generated_at": "2024-01-23T15:45:00Z"
    },
    "generation_time_seconds": 78
}
```

### POST `/ghl/webhook/listing-created`
**Purpose**: Handle new listing creation in GHL
**Trigger**: GHL opportunity.created webhook

**Request Body:**
```json
{
    "listing_id": "listing_12345",
    "contact_id": "contact_67890",
    "property_address": "123 Oak Street, Dallas, TX 75201",
    "list_price": 565000,
    "listing_date": "2024-01-23",
    "mls_number": "MLS123456"
}
```

**Response:**
```json
{
    "status": "marketing_plan_created",
    "tasks_created": 5,
    "marketing_strategy": {
        "photography_scheduled": "2024-01-25T10:00:00Z",
        "social_media_campaign": "active",
        "price_review_date": "2024-02-06T10:00:00Z"
    },
    "performance_tracking": {
        "views_target": 500,
        "showings_target": 8,
        "dom_target": 25
    }
}
```

## 🏡 Buyer Bot API

### POST `/ghl/webhook/new-buyer`
**Purpose**: Handle new buyer inquiry from GHL
**Trigger**: GHL contact.created with buyer tags

**Request Body:**
```json
{
    "id": "contact_id_11111",
    "name": "Mike Davis",
    "email": "mike@example.com",
    "phone": "+1555123456",
    "preferences": {
        "budget_min": 350000,
        "budget_max": 450000,
        "bedrooms": 3,
        "bathrooms": 2,
        "location": "North Dallas",
        "property_type": "single_family",
        "must_haves": ["garage", "backyard"],
        "nice_to_haves": ["pool", "updated_kitchen"]
    },
    "timeline": "60_days",
    "financing_status": "preapproved"
}
```

**Response:**
```json
{
    "status": "profile_created",
    "matches_found": 12,
    "buyer_score": 95,
    "recommendations": [
        {
            "property_id": "prop_67890",
            "address": "456 Pine Avenue, Dallas, TX 75202",
            "price": 425000,
            "match_score": 94,
            "key_features": ["3 bed", "2 bath", "2-car garage", "large backyard"],
            "showing_priority": "high"
        }
    ],
    "next_actions": [
        {"type": "send_property_recommendations", "count": 5},
        {"type": "schedule_showing", "property_id": "prop_67890"}
    ]
}
```

### POST `/ghl/webhook/property-viewed`
**Purpose**: Handle buyer property viewing/interaction
**Trigger**: Custom GHL webhook or manual trigger

**Request Body:**
```json
{
    "buyer_id": "contact_id_11111",
    "property_id": "prop_67890",
    "interaction_type": "virtual_tour_viewed",
    "duration_minutes": 8,
    "timestamp": "2024-01-23T16:00:00Z",
    "feedback": {
        "rating": 4,
        "comments": "Love the kitchen, but worried about the commute"
    }
}
```

**Response:**
```json
{
    "status": "preferences_updated",
    "learning_applied": true,
    "preference_changes": {
        "kitchen_importance": "+15%",
        "commute_concern": "high",
        "location_flexibility": "reduced"
    },
    "new_matches": 3,
    "refined_recommendations": [
        {
            "property_id": "prop_78901",
            "match_improvement": "+12%",
            "reason": "Better commute, similar kitchen features"
        }
    ]
}
```

## 🎛️ Command Center API

### GET `/metrics/unified`
**Purpose**: Get unified metrics from all three bots

**Response:**
```json
{
    "overview": {
        "active_leads": 146,
        "active_listings": 8,
        "active_buyers": 23,
        "total_revenue_potential": 2340000,
        "today_priorities": 5
    },
    "lead_bot": {
        "hot_leads": 23,
        "conversion_rate": "32%",
        "avg_response_time": "3.2 minutes"
    },
    "seller_bot": {
        "active_listings": 8,
        "avg_days_on_market": 22,
        "cma_generated_today": 4
    },
    "buyer_bot": {
        "active_buyers": 23,
        "properties_matched_today": 47,
        "showings_scheduled": 12
    },
    "claude_insights": [
        "Sarah Johnson (seller) property matches Mike Davis (buyer) criteria - potential internal sale",
        "Oak Street listing 14 days on market - consider 3% price adjustment",
        "3 hot leads need immediate follow-up within next 2 hours"
    ]
}
```

### POST `/claude/chat`
**Purpose**: Chat with Claude Concierge
**Features**: Cross-bot context, intelligent recommendations

**Request Body:**
```json
{
    "message": "What should I prioritize today?",
    "user_id": "jorge",
    "context": {
        "current_section": "command_center",
        "recent_actions": ["viewed_lead_dashboard", "checked_listings"]
    }
}
```

**Response:**
```json
{
    "response": "Based on your activity, here are today's priorities:\n\n1. **Hot Lead Alert**: Sarah Martinez (score: 97) responded 3 minutes ago - call immediately for 10x conversion\n2. **Internal Match**: Your Oak Street listing matches buyer Mike Davis perfectly - schedule showing today\n3. **Price Review**: 2 listings over 21 days on market need pricing strategy review\n\nShould I help you with any of these priorities?",
    "suggested_actions": [
        {"type": "call_lead", "lead_id": "contact_12345", "priority": "urgent"},
        {"type": "schedule_showing", "listing_id": "listing_67890", "buyer_id": "contact_11111"},
        {"type": "review_pricing", "listing_ids": ["listing_11111", "listing_22222"]}
    ],
    "context_updated": true
}
```

## 🔗 GHL Integration Webhooks

### Webhook Security
All webhooks must include signature validation:

```http
POST /webhook/endpoint
Content-Type: application/json
X-GHL-Signature: sha256=hash_of_payload

{
    "webhook_data": "..."
}
```

### Required GHL Custom Fields Setup

**Lead Fields:**
```json
{
    "lead_score": {"type": "number", "range": "0-100"},
    "lead_temperature": {"type": "dropdown", "options": ["hot", "warm", "cold"]},
    "ai_analysis_date": {"type": "datetime"}
}
```

**Seller Fields:**
```json
{
    "estimated_value": {"type": "number"},
    "cma_generated": {"type": "boolean"},
    "days_on_market_target": {"type": "number"}
}
```

**Buyer Fields:**
```json
{
    "buyer_score": {"type": "number", "range": "0-100"},
    "properties_matched": {"type": "number"},
    "last_showing_date": {"type": "date"}
}
```

## 🚨 Error Handling

### Standard Error Response Format
```json
{
    "error": {
        "code": "LEAD_ANALYSIS_FAILED",
        "message": "Failed to analyze lead due to missing budget information",
        "details": {
            "missing_fields": ["budget_min", "budget_max"],
            "retry_possible": true
        },
        "timestamp": "2024-01-23T16:30:00Z",
        "request_id": "req_12345"
    }
}
```

### Common Error Codes

| Code | Description | Action |
|------|-------------|---------|
| `RATE_LIMIT_EXCEEDED` | API rate limit reached | Retry after delay |
| `WEBHOOK_SIGNATURE_INVALID` | GHL webhook signature validation failed | Check webhook secret |
| `CLAUDE_API_ERROR` | Claude AI service unavailable | Fallback to rule-based logic |
| `PROPERTY_DATA_UNAVAILABLE` | Zillow API failed | Use cached data or manual input |
| `LEAD_ANALYSIS_FAILED` | Missing required lead data | Request manual data completion |

## 🔄 Rate Limiting

### API Rate Limits
- **Lead Bot**: 100 requests/minute per user
- **Seller Bot**: 50 requests/minute (CMA generation is expensive)
- **Buyer Bot**: 100 requests/minute per user
- **Claude API**: Managed internally with queue system

### GHL Integration Limits
- **Incoming Webhooks**: No limit (we control processing)
- **Outgoing API Calls**: 100 requests/10 seconds, 200K/day
- **Implementation**: Async queue with intelligent batching

---

**All endpoints include comprehensive logging, monitoring, and performance tracking to ensure the 5-minute response requirement for maximum conversion rates.**