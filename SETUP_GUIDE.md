# Jorge's Real Estate AI Bots - Setup Guide

**Welcome to your AI-powered real estate automation platform!**

This guide will get you from zero to running in 30 minutes.

---

## 🎯 What You're Getting

### Phase 1 MVP - Lead Bot (✅ Built)
- **5-Minute Response Rule**: Automatic lead qualification within 5 minutes
- **AI Lead Scoring**: Claude AI analyzes each lead (0-100 score)
- **Temperature Classification**: Hot/Warm/Cold automatic routing
- **GHL Integration**: Updates custom fields automatically
- **Immediate Follow-up**: Sends alerts based on lead temperature

### Coming Soon
- **Seller Bot**: CMA generation in <90 seconds
- **Buyer Bot**: AI property matching
- **Command Center**: Unified dashboard

---

## 📋 Prerequisites

### 1. Required API Keys

You need these API keys before starting. Get them from:

| Service | Where to Get | Cost |
|---------|-------------|------|
| **Claude AI** | https://console.anthropic.com/ | ~$150/month (1000 leads) |
| **GoHighLevel** | Settings → Integrations → API | Included with Agency Pro |
| **Zillow API** | https://www.zillow.com/howto/api/ | $500/month |
| **Twilio** | https://www.twilio.com/console | ~$50/month |
| **SendGrid** | https://app.sendgrid.com/settings/api_keys | Free tier available |

### 2. System Requirements

- Python 3.11 or higher
- Redis (for <500ms caching)
- PostgreSQL (for data storage)
- 2GB RAM minimum

---

## 🚀 Quick Start (30 Minutes)

### Step 1: Clone and Setup (5 min)

```bash
# Navigate to project
cd ~/Documents/GitHub/jorge_real_estate_bots

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Mac/Linux
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment (10 min)

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your favorite editor
nano .env  # or vi, code, etc.
```

**Fill in these CRITICAL variables:**

```bash
# Claude AI (REQUIRED)
ANTHROPIC_API_KEY=sk-ant-your_key_here

# GoHighLevel (REQUIRED)
GHL_API_KEY=your_ghl_api_key
GHL_LOCATION_ID=your_location_id

# Zillow (for future Seller Bot)
ZILLOW_API_KEY=your_zillow_key

# Twilio SMS (REQUIRED)
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890

# SendGrid Email (REQUIRED)
SENDGRID_API_KEY=your_sendgrid_key
```

### Step 3: Start Database Services (5 min)

**Option A: Using Docker (Recommended)**

```bash
# Start Redis and PostgreSQL
docker-compose up -d

# Verify they're running
docker ps
```

**Option B: Local Installation**

```bash
# Install Redis
brew install redis  # Mac
redis-server  # Start Redis

# Install PostgreSQL
brew install postgresql  # Mac
postgres -D /usr/local/var/postgres  # Start PostgreSQL
```

### Step 4: Test the Setup (5 min)

```bash
# Run health check
python -c "from bots.shared.config import settings; print(f'✅ Config loaded! Environment: {settings.environment}')"

# Test Claude AI connection
python -c "from bots.shared.claude_client import ClaudeClient; c = ClaudeClient(); print('✅ Claude client initialized')"

# Test GHL connection
python -c "from bots.shared.ghl_client import GHLClient; c = GHLClient(); print(c.health_check())"
```

### Step 5: Start Lead Bot (5 min)

```bash
# Start Lead Bot on port 8001
python -m uvicorn bots.lead_bot.main:app --host 0.0.0.0 --port 8001 --reload
```

You should see:

```
🔥 Starting Lead Bot...
Environment: development
5-Minute Response Timeout: 300s
✅ Lead Bot ready!
INFO:     Uvicorn running on http://0.0.0.0:8001
```

**Test the API:**

Open browser: http://localhost:8001/health

You should see:

```json
{
  "status": "healthy",
  "service": "lead_bot",
  "version": "1.0.0",
  "5_minute_rule": {
    "timeout_seconds": 300,
    "target_ms": 500
  }
}
```

---

## 🔗 GoHighLevel Integration

### 1. Create Custom Fields

In GHL: `Settings → Custom Fields → Contact Fields`

Create these fields:

| Field Name | Type | Options |
|-----------|------|---------|
| `ai_lead_score` | Number | 0-100 |
| `lead_temperature` | Dropdown | hot, warm, cold |
| `budget_min` | Number | - |
| `budget_max` | Number | - |
| `timeline` | Dropdown | ASAP, 30, 60, 90, 180+ |
| `financing_status` | Dropdown | preapproved, exploring, not_started |

### 2. Configure Webhook

In GHL: `Settings → Integrations → Webhooks`

**Create Webhook:**
- Name: "Jorge Bots - New Lead"
- URL: `http://your-domain.com/ghl/webhook/new-lead` (or use ngrok for testing)
- Events: ☑️ Contact Create
- Method: POST

**For local testing with ngrok:**

```bash
# Install ngrok (https://ngrok.com/)
ngrok http 8001

# Copy the https URL (e.g., https://abc123.ngrok.io)
# Use in GHL webhook: https://abc123.ngrok.io/ghl/webhook/new-lead
```

### 3. Test Integration

**Create a test contact in GHL:**

1. Go to Contacts → Add Contact
2. Name: "Test Lead"
3. Email: test@example.com
4. Source: website

**Expected Result:**

Within seconds, you should see:
1. Webhook fired to Lead Bot ✅
2. Lead analyzed by Claude AI ✅
3. Custom fields updated (ai_lead_score, lead_temperature) ✅
4. Follow-up message sent ✅

**Check Lead Bot logs:**

```
📨 New lead webhook received: abc123
Analyzing lead: abc123
✅ Lead analysis: 342.5ms
🎯 Lead abc123 processed in 584.2ms (Score: 75, Temp: warm)
📬 Follow-up sent for abc123 (warm)
```

---

## 📊 Understanding Lead Scoring

### Scoring Criteria (0-100)

| Criteria | Max Points | Description |
|----------|-----------|-------------|
| **Price Range** | 30 | Within $200K-$800K range |
| **Location** | 25 | In Dallas/Plano/Frisco/McKinney/Allen |
| **Timeline** | 20 | ASAP or <60 days |
| **Motivation** | 15 | Pre-approved, strong signals |
| **Contact Quality** | 10 | Complete info + specific needs |

### Temperature Assignment

| Score | Temperature | Action |
|-------|------------|--------|
| **80-100** | 🔥 HOT | Call within 1 hour |
| **60-79** | ⚠️ WARM | Follow up within 24 hours |
| **0-59** | 📊 COLD | Add to nurture sequence |

---

## 🎯 Validating the 5-Minute Rule

The #1 priority is the 5-minute response rule (10x conversion multiplier).

### How to Verify Compliance

1. **Check Lead Bot Logs:**

```bash
# Monitor real-time logs
tail -f lead_bot.log

# Look for:
# ✅ Lead analysis: <500ms
# 🎯 Lead processed in <1000ms
```

2. **Check Performance Metrics:**

```bash
# API endpoint
curl http://localhost:8001/metrics
```

3. **Monitor GHL Timestamps:**

In GHL, check:
- Lead creation time
- Custom field update time
- Time difference should be <30 seconds

---

## 🚨 Troubleshooting

### "ModuleNotFoundError: No module named 'bots'"

**Solution:**

```bash
# Make sure you're in the project root
cd ~/Documents/GitHub/jorge_real_estate_bots

# Make sure virtual environment is activated
source venv/bin/activate
```

### "GHL_API_KEY not found"

**Solution:**

```bash
# Verify .env file exists
ls -la .env

# Check if variables are set
cat .env | grep GHL_API_KEY

# Reload environment
source .env  # or restart terminal
```

### "Redis connection failed"

**Solution:**

```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# If not running:
docker-compose up -d redis
# or
redis-server
```

### "Claude API error: Unauthorized"

**Solution:**

```bash
# Verify API key
echo $ANTHROPIC_API_KEY

# Test manually
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```

### Lead analysis taking >500ms

**Possible causes:**

1. **No Redis caching** - Check Redis connection
2. **Large system prompt** - Should be cached after first call
3. **Network latency** - Check Claude API latency
4. **Model routing** - Verify using Sonnet, not Opus

---

## 📈 Next Steps

### Phase 1 Completion Checklist

- [x] Lead Bot MVP built
- [ ] Test with 10-20 real leads from Jorge's GHL
- [ ] Validate lead scores against Jorge's manual assessment
- [ ] Measure actual response times and conversion tracking
- [ ] Fine-tune Claude prompts based on results
- [ ] Achieve >85% qualification accuracy
- [ ] Maintain >99% 5-minute compliance

### Phase 1 Month 2: Seller Bot

- [ ] Build CMA automation engine
- [ ] Integrate Zillow API for property data
- [ ] Create PDF report generation
- [ ] Target: <90 second CMA generation

### Phase 1 Month 3: Buyer Bot + Command Center

- [ ] Build property matching engine
- [ ] Create behavioral learning system
- [ ] Build Streamlit command center
- [ ] Integrate Claude concierge

---

## 💰 Expected ROI

### Jorge's Business Impact

| Metric | Current (Manual) | Target (AI Bots) | Improvement |
|--------|------------------|------------------|-------------|
| **Response Time** | 47 minutes | <5 minutes | 10x conversion rate |
| **Contact Rate** | 38% | 83% | +118% |
| **Conversion Rate** | 15% | 32% | +113% |
| **Monthly Commission** | Baseline | +$24K | Jorge's revenue increase |

### Platform Economics

- **Operating Costs**: $1,222-1,297/month
- **Break-even**: 5-15 agents
- **Target ARR**: $1M in 18-24 months

---

## 📞 Support

For issues or questions:

1. **Check Documentation**: See all `.md` files in project root
2. **Review Logs**: `tail -f lead_bot.log`
3. **Test Health Endpoints**: `curl http://localhost:8001/health`
4. **Check Environment**: `python -c "from bots.shared.config import settings; print(vars(settings))"`

---

**🎉 Congratulations! You're ready to start automating Jorge's real estate business with AI.**

**Remember**: The 5-minute response rule is your #1 priority. Everything else is secondary.
