# Jorge Real Estate Bots

## Stack
Python 3.11+ | FastAPI | Redis | Anthropic Claude | GoHighLevel API

## Architecture
Three AI bots (Lead, Buyer, Seller) in a single FastAPI app using APIRouter pattern.
- Entry: `bots/lead_bot/main.py` (includes all routers)
- Routes: `routes_webhook.py`, `routes_dashboard.py`, `routes_admin.py`, `routes_realtime.py`, `routes_productization.py`, `routes_test_endpoints.py`
- Shared: `bots/shared/` -- config, cache, GHL client, Claude client, funnel_attribution, stall_reengagement, bot_metrics_collector, alerting_service, sms_metrics_collector, response_filter, rate_limit_middleware, business_rules
- Bots: `bots/seller_bot/`, `bots/buyer_bot/`

## Deploy
- Live: jorge-realty-ai-xxdf.onrender.com (Render srv-d6d5go15pdvs73fcjjq0)
- Redis: red-d6d54jfpm1nc739jgnm0:6379
- Blueprint: `render.yaml`

## Test
```
pytest tests/ -v  # 1,824 tests
```

## Key Env
REDIS_URL, GHL_API_KEY, ADMIN_API_KEY, ANTHROPIC_API_KEY, GHL_LOCATION_ID, JORGE_USER_ID, JORGE_CALENDAR_ID
