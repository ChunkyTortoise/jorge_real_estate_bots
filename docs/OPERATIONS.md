# Operations Runbook

Concise operations guide for the Jorge Real Estate Bots deployment.

**Live URL:** `https://jorge-realty-ai-xxdf.onrender.com`
**Render Service:** `srv-d6d5go15pdvs73fcjjq0`

---

## 1. Health Checks

**Basic health:**

```bash
curl https://jorge-realty-ai-xxdf.onrender.com/health
```

Expected: `{"status": "healthy"}`

**Aggregate health (includes Redis and DB status):**

```bash
curl https://jorge-realty-ai-xxdf.onrender.com/health/aggregate \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

Expected: `{"status": "healthy", "db_ok": true, "redis_ok": true, ...}`

If `redis_ok` is false, conversation state and rate limiting will not work. If `db_ok` is false, persistent storage is down.

---

## 2. Reset Stuck Conversation

When a contact is stuck in a loop or has corrupted state:

1. Identify the contact ID from GHL or the dashboard
2. Reset the bot state:

```bash
# Reset lead bot state
curl -X DELETE https://jorge-realty-ai-xxdf.onrender.com/admin/reset-state/lead/CONTACT_ID \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"

# Reset buyer bot state
curl -X DELETE https://jorge-realty-ai-xxdf.onrender.com/admin/reset-state/buyer/CONTACT_ID \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"

# Reset seller bot state
curl -X DELETE https://jorge-realty-ai-xxdf.onrender.com/admin/reset-state/seller/CONTACT_ID \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

3. The next message from the contact will start a fresh conversation flow.

---

## 3. Reassign Contact to Different Bot

Option A -- **Via admin API:**

```bash
curl -X POST https://jorge-realty-ai-xxdf.onrender.com/admin/reassign-bot \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -d '{"contact_id": "CONTACT_ID", "target_bot": "buyer"}'
```

Valid `target_bot` values: `lead`, `buyer`, `seller`.

Option B -- **Via GHL:**

1. Open the contact in GoHighLevel
2. Update the `customData.botType` field to `buyer`, `seller`, or `lead`
3. The next incoming message will route to the new bot

---

## 4. Manual Takeover

When a human agent needs to take over a conversation:

1. In GoHighLevel, add the **"Jorge-Active"** tag to the contact
2. The bot will stop responding to that contact's messages
3. The human agent handles the conversation directly in GHL

**To re-enable the bot:** Remove the "Jorge-Active" tag from the contact.

---

## 5. Deploy Procedure

Deployments are triggered by pushing to the `main` branch on GitHub.

1. Ensure all tests pass locally:
   ```bash
   pytest tests/ -v
   ```
2. Commit and push to `main`:
   ```bash
   git add .
   git commit -m "description of changes"
   git push origin main
   ```
3. GitHub Actions CI runs the test suite automatically
4. On CI success, the deploy workflow triggers a Render deploy
5. Render builds from the GitHub git SHA (not Docker Hub)
6. Monitor the deploy at: https://dashboard.render.com/web/srv-d6d5go15pdvs73fcjjq0
7. Verify the deploy with a health check:
   ```bash
   curl https://jorge-realty-ai-xxdf.onrender.com/health
   ```

**Important:** Render builds from GitHub, so you must `git push` to trigger a deploy. Building a Docker image locally and pushing to Docker Hub will not trigger a Render deploy.

---

## 6. Rollback Procedure

If a deploy introduces issues:

1. Go to the Render dashboard: https://dashboard.render.com/web/srv-d6d5go15pdvs73fcjjq0
2. Click **Events** in the left sidebar
3. Find the previous successful deploy
4. Click the **three dots** menu on that deploy and select **Rollback to this deploy**
5. Render will redeploy the previous version
6. Verify with a health check after rollback completes

---

## 7. Redis/DB Status

Check via the aggregate health endpoint:

```bash
curl https://jorge-realty-ai-xxdf.onrender.com/health/aggregate \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

**Redis** (`red-d6d54jfpm1nc739jgnm0:6379`):
- Stores conversation state, rate limit counters, funnel events, bot settings
- If Redis is down: bots will still respond but cannot maintain conversation state or enforce rate limits
- Render Redis dashboard: check the Redis instance in the Render dashboard for memory usage and connection count

**PostgreSQL:**
- Stores persistent lead data and analytics
- If DB is down: bots can still respond via Redis, but data will not be persisted long-term

---

## 8. Monitoring

### UptimeRobot Setup

1. Create a free account at [uptimerobot.com](https://uptimerobot.com)
2. Add a new monitor:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** Jorge Realty AI
   - **URL:** `https://jorge-realty-ai-xxdf.onrender.com/health`
   - **Monitoring Interval:** 5 minutes
3. Set up alert contacts (email, Slack, etc.) to be notified on downtime
4. Expected response: HTTP 200 with `{"status": "healthy"}`

### What to monitor

| Endpoint | Interval | Alert if |
|----------|----------|----------|
| `/health` | 5 min | Non-200 response or timeout |
| `/health/aggregate` | 15 min | `redis_ok: false` or `db_ok: false` |

### Render auto-restart

Render automatically restarts the service if the health check (`/health`) fails. The `render.yaml` has `healthCheckPath: /health` configured.
