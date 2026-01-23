# Jorge's Real Estate AI Bots - Quick Start Guide

**Get Jorge's platform running in 30 minutes**

## 🎯 What You're Building

Three AI-powered bots that integrate with Jorge's GoHighLevel CRM:
- **🔥 Lead Bot**: <5 minute response time (10x conversion boost)
- **💰 Seller Bot**: <90 second CMA generation (vs 2-4 hours manual)
- **🏡 Buyer Bot**: Intelligent property matching and learning
- **🎛️ Command Center**: Unified dashboard with Claude concierge

**Expected ROI**: +$24K monthly for Jorge from response time improvement alone

---

## ⚡ 15-Minute Local Setup

### Step 1: Clone and Setup Environment
```bash
# Clone repository (when available)
git clone <repository-url>
cd jorge_real_estate_bots

# Copy environment template
cp .env.example .env

# Edit environment file with your API keys
nano .env
```

### Step 2: Required API Keys (Get These First)
```bash
# CRITICAL - Get these immediately:
ANTHROPIC_API_KEY=     # https://console.anthropic.com/
GHL_API_KEY=          # GoHighLevel → Settings → Integrations → API
ZILLOW_API_KEY=       # https://www.zillow.com/howto/api/
TWILIO_ACCOUNT_SID=   # https://www.twilio.com/console
SENDGRID_API_KEY=     # https://app.sendgrid.com/settings/api_keys
```

### Step 3: Start Services
```bash
# Install dependencies
pip install -r requirements.txt

# Start database services
docker-compose up -d postgres redis

# Run database migrations
alembic upgrade head

# Start all bots (separate terminals)
python -m uvicorn bots.lead_bot.main:app --port 8001 --reload
python -m uvicorn bots.seller_bot.main:app --port 8002 --reload
python -m uvicorn bots.buyer_bot.main:app --port 8003 --reload

# Start command center
streamlit run command_center/main.py --server.port 8501
```

### Step 4: Verify Everything Works
```bash
# Test each service
curl http://localhost:8001/health  # Lead Bot
curl http://localhost:8002/health  # Seller Bot
curl http://localhost:8003/health  # Buyer Bot
open http://localhost:8501         # Command Center
```

**✅ Success**: All services respond, Command Center loads, Claude greets you

---

## 🔗 GoHighLevel Integration (30 Minutes)

### Step 1: GHL Custom Fields Setup
Navigate to: `Settings → Custom Fields → Contact Fields`

**Create these fields exactly:**
```json
{
    "ai_lead_score": {"type": "Number", "label": "AI Lead Score (0-100)"},
    "lead_temperature": {"type": "Dropdown", "options": ["hot", "warm", "cold"]},
    "estimated_property_value": {"type": "Number", "label": "AI Estimated Value"},
    "cma_generated": {"type": "Checkbox", "label": "CMA Generated"},
    "buyer_score": {"type": "Number", "label": "Buyer Score (0-100)"}
}
```

### Step 2: Webhook Configuration
Navigate to: `Settings → Integrations → Webhooks`

**Create these webhooks:**
1. **New Lead Webhook**
   - Name: "Jorge Bots - New Lead"
   - URL: `https://your-domain.com/lead_bot/ghl/webhook/new-lead`
   - Events: `ContactCreate`
   - Method: `POST`

2. **Seller Inquiry Webhook**
   - Name: "Jorge Bots - Seller Inquiry"
   - URL: `https://your-domain.com/seller_bot/ghl/webhook/new-seller`
   - Events: `ContactCreate`
   - Tags Filter: `seller, listing_inquiry`

### Step 3: Pipeline Setup
Navigate to: `CRM → Pipelines → Create Pipeline`

**Lead Pipeline Stages:**
1. New Lead → (triggers AI analysis)
2. AI Qualified - Hot → (immediate call task)
3. AI Qualified - Warm → (24hr follow-up)
4. AI Qualified - Cold → (weekly nurture)
5. Appointment Scheduled
6. Under Contract
7. Closed

### Step 4: Test Integration
```bash
# Create test contact in GHL with these details:
Name: Test Lead
Email: test@example.com
Source: website
Tags: lead

# Expected result:
# - Webhook fires to Lead Bot
# - Lead gets analyzed and scored
# - Custom fields updated in GHL
# - Pipeline stage moved based on score
# - Follow-up task created for Jorge
```

**✅ Success**: Test lead appears in Command Center with AI analysis

---

## 🔥 Phase 1 Development Priority (Month 1)

### Week 1-2: Lead Bot Core
- [ ] **Critical Path**: 5-minute response enforcement
- [ ] Claude integration for lead analysis
- [ ] GHL webhook processing
- [ ] Automated SMS/Email sequences
- [ ] Task creation for Jorge

**Success Criteria:**
- Lead analysis: <500ms
- GHL integration: <1% error rate
- Jorge feedback: "This saves me time"

### Week 3-4: Seller Bot CMA Engine
- [ ] Zillow API integration
- [ ] Claude-powered pricing analysis
- [ ] PDF report generation
- [ ] Automated CMA delivery via GHL

**Success Criteria:**
- CMA generation: <90 seconds
- Jorge feedback: "CMAs better than manual"

### Month 1 Validation Checkpoint
- [ ] ✅ Jorge using platform daily
- [ ] ✅ Measurable time savings (60%+)
- [ ] ✅ Lead conversion improvement (50%+)
- [ ] ✅ Platform stability (99%+ uptime)

---

## 📊 Monitoring Setup (5 Minutes)

### Essential Monitoring
```python
# Add to all bot main.py files
import time
import logging

# Performance tracking
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)

    # Alert if response time > 5 minutes (critical for leads)
    if "/webhook/new-lead" in str(request.url) and process_time > 300:
        logging.error(f"CRITICAL: Lead response time {process_time}s > 5 minutes!")

    return response
```

### Key Metrics to Track
- **Lead Response Time**: Must be <300 seconds (5 minutes)
- **Lead Qualification Accuracy**: >85% vs Jorge's manual assessment
- **CMA Generation Time**: <90 seconds target
- **API Error Rate**: <1% for all services
- **Jorge Satisfaction**: Daily usage + feedback

---

## 🚨 Troubleshooting Common Issues

### "Claude API Error"
```bash
# Check API key
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" https://api.anthropic.com/v1/messages

# Common fixes:
# 1. Verify API key in .env
# 2. Check rate limits (1000 requests/day free tier)
# 3. Verify model name: claude-3-5-sonnet-20241022
```

### "GHL Webhook Not Firing"
```bash
# Test webhook endpoint directly
curl -X POST http://localhost:8001/ghl/webhook/new-lead \
  -H "Content-Type: application/json" \
  -d '{"id": "test", "name": "Test Lead", "email": "test@example.com"}'

# Common fixes:
# 1. Verify webhook URL is accessible (not localhost for GHL)
# 2. Check webhook secret matches
# 3. Ensure contact meets filter criteria
# 4. Verify webhook events are selected
```

### "Database Connection Error"
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Test connection
python -c "import psycopg2; conn = psycopg2.connect('$DATABASE_URL'); print('Connected!')"

# Common fixes:
# 1. Start database: docker-compose up -d postgres
# 2. Check DATABASE_URL in .env
# 3. Run migrations: alembic upgrade head
```

### "Command Center Won't Load"
```bash
# Check if Streamlit is running
curl http://localhost:8501

# Check logs
streamlit run command_center/main.py --logger.level debug

# Common fixes:
# 1. Install streamlit: pip install streamlit
# 2. Check port 8501 isn't in use: lsof -i :8501
# 3. Verify bot services are running first
```

---

## 📋 Pre-Production Checklist

### Jorge Business Validation
- [ ] Jorge has provided real lead data for testing
- [ ] Current baseline metrics documented (response time, conversion rate)
- [ ] Jorge's GHL account has proper permissions (API, webhooks, custom fields)
- [ ] Success criteria agreed upon (+$24K monthly target)

### Technical Validation
- [ ] All API keys working and tested
- [ ] GHL integration complete and tested with real webhooks
- [ ] Claude AI providing quality lead analysis (Jorge approved)
- [ ] CMA generation accurate within 10% of market values
- [ ] 5-minute response rule enforced and monitored

### Production Readiness
- [ ] Error handling and logging comprehensive
- [ ] Performance monitoring in place (DataDog/Sentry)
- [ ] Backup and recovery procedures documented
- [ ] Security best practices implemented (HTTPS, secrets management)
- [ ] Deployment pipeline tested (staging → production)

---

## 🎯 Success Milestones

### Week 1 Success
- [ ] Local development environment operational
- [ ] Basic GHL integration working
- [ ] Jorge can see AI analysis in his GHL dashboard

### Month 1 Success
- [ ] Jorge using platform daily without issues
- [ ] Measurable improvement in response times (manual 47min → AI <5min)
- [ ] Lead conversion rate improved by 50%+
- [ ] Jorge testimonial: "This is saving me hours every day"

### Month 3 Success
- [ ] All three bots operational and integrated
- [ ] Jorge's monthly revenue increased by $24K+
- [ ] Platform ready for multi-tenant expansion
- [ ] Path to $1M ARR clearly defined

---

## 📚 Next Steps

1. **Start Today**: Set up local environment and get Claude API working
2. **Day 2-3**: Complete GHL integration and test with Jorge's real data
3. **Week 1**: Focus on Lead Bot - this has highest ROI impact
4. **Week 2-4**: Build Seller Bot for CMA automation
5. **Month 2**: Add Buyer Bot and complete Command Center
6. **Month 3**: Optimize and prepare for scaling to other agents

---

## 📞 Getting Help

### Critical Support (Response Time Issues)
- **Email**: jorge-bots-emergency@example.com
- **Phone**: Available during setup phase
- **Slack**: #jorge-bots-dev channel

### Documentation
- `SPECIFICATION.md` - Complete technical specification
- `API_DOCUMENTATION.md` - All API endpoints and usage
- `GHL_INTEGRATION.md` - Detailed GoHighLevel setup guide
- `DEPLOYMENT_GUIDE.md` - Production deployment instructions
- `DEVELOPMENT_CHECKLIST.md` - Phase-by-phase development tasks

### Success Metrics Dashboard
Once running, access these URLs:
- **Command Center**: http://localhost:8501
- **Lead Bot API**: http://localhost:8001/docs
- **Seller Bot API**: http://localhost:8002/docs
- **Buyer Bot API**: http://localhost:8003/docs

---

**🎯 Remember**: The #1 priority is the 5-minute lead response rule. This single metric drives the 10x conversion multiplier and Jorge's $24K monthly revenue increase. Everything else is secondary.**