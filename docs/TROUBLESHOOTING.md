# Troubleshooting Guide

Common issues and solutions for the Jorge Real Estate Bots system.

---

## GHL Webhook Setup

### Webhooks not firing

1. **Verify the webhook URL is correct** in GHL Settings > Webhooks:
   - Production: `https://jorge-realty-ai-xxdf.onrender.com/api/ghl/webhook`
   - Local: `http://localhost:8001/api/ghl/webhook`

2. **Check the GHL workflow is active.** Go to Automations > Workflows and confirm "5. Process Message - Which Bot?" is published and enabled.

3. **Confirm the contact has a Bot Type custom field.** The unified webhook reads `Bot Type` from customData or the contact's custom fields to route to the correct bot. If missing, it defaults to Lead Bot.

### Webhook signature verification failures (401)

The system supports two signature schemes:

- **RSA (recommended):** Set `GHL_WEBHOOK_PUBLIC_KEY` env var with the PEM public key from GHL.
- **HMAC (legacy):** Set `GHL_WEBHOOK_SECRET` env var with the shared secret.

If neither is set, signature verification is skipped (pass-through mode). To debug:

```bash
# Check which scheme is configured
curl http://localhost:8001/health | jq .
# Look for signature-related warnings in logs
```

### Duplicate messages / double-processing

The unified webhook has built-in deduplication (5-minute TTL). If you see duplicates:

1. Check that Redis is running and connected (see Redis section below).
2. Verify GHL isn't sending the same webhook multiple times (check GHL webhook logs).
3. The dedup key is based on `contact_id + MD5(message_body)` -- identical messages within 5 minutes are skipped.

---

## Redis Connection Errors

### `ConnectionRefusedError` or `Connection closed`

1. **Verify Redis is running:**
   ```bash
   redis-cli ping    # Should return PONG
   ```

2. **Check the `REDIS_URL` environment variable:**
   ```bash
   echo $REDIS_URL
   # Expected format: redis://localhost:6379/0
   # Production: redis://red-d6d54jfpm1nc739jgnm0:6379
   ```

3. **Docker users:** Ensure the Redis container is running:
   ```bash
   docker compose ps redis
   docker compose logs redis
   ```

### Redis works but bot settings not persisting

Bot settings are stored in Redis under the key `admin:bot_settings` with a 90-day TTL. If settings disappear:

1. Check Redis memory usage: `redis-cli info memory`
2. Verify the cache service initialized: look for "Webhook cache initialized" in startup logs.
3. Manual check: `redis-cli GET admin:bot_settings`

### System works without Redis

The bots use an in-memory cache fallback when Redis is unavailable. Features affected:

- Message deduplication won't persist across restarts
- Rate limiting uses in-memory counters (per-process only)
- Bot settings overrides reset on restart
- WebSocket event broker falls back to local pubsub

---

## Environment Variable Checklist

Required for production:

| Variable | Description | Example |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `GHL_API_KEY` | GoHighLevel API key | `eyJ...` |
| `GHL_LOCATION_ID` | GHL location/sub-account ID | `abc123` |
| `JORGE_USER_ID` | Jorge's GHL user ID | `4lAS80xUq4MIRbgfQ5vg` |
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-...` |
| `JWT_SECRET` | Secret for auth tokens | (random 32+ char string) |
| `ADMIN_PASSWORD` | Dashboard admin password | (strong password) |

Optional:

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Runtime environment | `production` |
| `DEMO_MODE` | Run with mock data | `false` |
| `DATABASE_URL` | PostgreSQL connection | (none -- Postgres features disabled) |
| `GHL_WEBHOOK_SECRET` | HMAC webhook secret | (none -- verification skipped) |
| `GHL_WEBHOOK_PUBLIC_KEY` | RSA webhook public key | (none -- verification skipped) |
| `JORGE_CALENDAR_ID` | Calendar for booking | (none -- booking disabled) |

### Quick env validation

```bash
# Check all required vars are set
for var in REDIS_URL GHL_API_KEY GHL_LOCATION_ID JORGE_USER_ID ANTHROPIC_API_KEY JWT_SECRET ADMIN_PASSWORD; do
  if [ -z "${!var}" ]; then echo "MISSING: $var"; else echo "OK: $var"; fi
done
```

---

## Common HTTP Errors

### 401 Unauthorized

- **On webhook endpoints:** Signature verification failed. See "Webhook signature verification failures" above.
- **On API endpoints (`/analyze-lead`, `/performance`, `/metrics`):** Missing or invalid JWT token. Include `Authorization: Bearer <token>` header.
- **Quick fix for testing:** Set `ENVIRONMENT=test` and use `Authorization: Bearer test-token`.

### 429 Too Many Requests

The system enforces rate limits at two levels:

1. **Global IP-based:** `rate_limit_per_minute` (default: 60 req/min). Check `X-RateLimit-Remaining` response header.
2. **Per-user:** Applied after JWT auth. Same config values.
3. **Webhook-specific:** Per-minute limit on `/api/ghl/webhook`.

To increase limits, set `RATE_LIMIT_PER_MINUTE` and `RATE_LIMIT_PER_HOUR` env vars.

### 500 Internal Server Error

Check the application logs for the full traceback:

```bash
# Local
python jorge_launcher.py 2>&1 | grep ERROR

# Render
# Go to Dashboard > jorge-realty-ai > Logs
```

Common causes:
- Anthropic API key expired or invalid
- Redis connection lost mid-request
- GHL API rate limit hit (5000 req/day)

---

## Bot Handoff Failures

### Leads not routing to the correct bot

The unified webhook determines bot type in this order:

1. `customData.bot_type` in the webhook payload
2. `customData["Bot Type"]` in the webhook payload
3. `bot_type` field in the payload root
4. GHL contact custom field `Bot Type` (fetched via API)
5. Default: `lead` (Lead Bot)

**Fix:** Ensure the GHL workflow sets `Bot Type` in the customData before firing the webhook.

### Handoff confidence threshold

Cross-bot handoffs require a confidence score >= 0.7 (configurable). If leads aren't handing off:

1. Check the handoff service logs for confidence scores.
2. Lower the threshold in the handoff service config if needed.
3. Circular handoff prevention: a lead can't be handed back to a bot it came from.
4. Rate limits: max 3 handoffs/hour, 10/day per contact.

### Seller/Buyer bot "unavailable" errors

If you see `{"status": "error", "detail": "seller bot unavailable"}`:

1. Check startup logs for "Failed to initialize seller/buyer bots".
2. Common cause: missing or invalid `GHL_API_KEY`.
3. The bots initialize during app startup -- a failure there means the bot instance is `None`.

---

## Dashboard Issues

### Streamlit dashboard not loading

1. **Verify the dashboard is running:**
   ```bash
   streamlit run command_center/dashboard_v3.py --server.port 8501
   ```

2. **Check Redis connection** -- the dashboard reads metrics from Redis.

3. **Auth issues:** The dashboard uses its own Streamlit auth. Check `ADMIN_PASSWORD` is set.

### Metrics showing zeros

- Metrics are accumulated in-memory and reset on restart.
- The `/performance` endpoint tracks since last startup only.
- For persistent metrics, check the PostgreSQL database (if configured).

---

## Getting Help

1. Check the [Architecture Decision Records](adr/) for design context.
2. Review the [API Documentation](../README.md#api-documentation) for endpoint details.
3. Run the health check: `curl http://localhost:8001/health/aggregate`
4. Run tests to verify system integrity: `pytest tests/ -v`
