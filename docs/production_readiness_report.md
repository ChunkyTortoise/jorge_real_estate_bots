# Jorge Production Readiness Report

- Base URL: `https://jorge-realty-ai-xxdf.onrender.com`
- Contact ID: `(none provided)`
- Overall result: `review required`

| Check | Result | Details |
|---|---|---|
| GET /health | PASS | HTTP 200: {"status": "healthy", "service": "lead_bot", "timestamp": "2026-03-06T23:25:50.747906", "version": "1.0.0", "environment": "staging", "5_minute_rule": {"timeout_seconds": 300, "target_ms": 500}} |
| GET /health status | PASS | status='healthy', expected='healthy' |
| GET /health environment | FAIL | environment='staging', expected='production' |
| GET /health/aggregate | PASS | HTTP 200: {"status": "degraded", "services": {"lead_bot": "ok", "seller_bot": "ok", "buyer_bot": "ok", "redis": "ok", "postgres": "down"}, "timestamp": "2026-03-06T23:25:50.921432+00:00"} |
| GET /health/aggregate status | FAIL | status='degraded', expected='healthy' |
| GET /admin/settings | PASS | HTTP 200: {"seller": {"system_prompt": "You are Jorge, a friendly cash home buyer in Rancho Cucamonga. Keep responses under 100 words, warm and conversational. Focus entirely on helping the seller understand their options. Treat every dollar amount the seller mentions as their asking price. When unsure, redir |
| GET /api/dashboard/leads/summary | PASS | HTTP 200: {"hero": {"total_leads": 0, "qualified_leads": 0, "hot_leads": 0, "active_conversations": 0, "revenue_30_day": 0, "revenue_forecast": 0, "lead_source_roi": {"referrals": {"roi": "infinite", "leads": 0, "cost": 0}, "google_ads": {"roi": 0, "leads": 0, "cost": 0}, "facebook": {"roi": 0, "leads": 0, "c |
| GET /api/dashboard/leads | FAIL | HTTP 500: Internal Server Error |
