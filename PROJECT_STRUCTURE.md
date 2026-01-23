# Jorge's Real Estate AI Bots - Complete Project Structure

**Reference guide for the complete codebase organization**

## 📁 Top-Level Directory Structure

```
Jorge_Real_Estate_Bots/
├── README.md                          # Project overview and quick links
├── SPECIFICATION.md                   # Complete technical specification
├── API_DOCUMENTATION.md               # All API endpoints and usage
├── GHL_INTEGRATION.md                 # GoHighLevel setup guide
├── DEVELOPMENT_CHECKLIST.md           # Phase-by-phase development tasks
├── DEPLOYMENT_GUIDE.md                # Production deployment instructions
├── QUICK_START.md                     # 30-minute setup guide
├── PROJECT_STRUCTURE.md               # This file - complete structure
├── .env.example                       # Environment configuration template
├── .gitignore                         # Git ignore patterns
├── requirements.txt                   # Python dependencies
├── requirements-dev.txt               # Development dependencies
├── docker-compose.yml                 # Local development services
├── Dockerfile                         # Container definition
├── alembic.ini                        # Database migration configuration
└── jorge_launcher.py                  # Single-file startup script
```

---

## 🤖 Core Application Structure

```
jorge_real_estate_bots/
├── bots/
│   ├── __init__.py
│   ├── shared/                        # Common utilities and services
│   │   ├── __init__.py
│   │   ├── claude_client.py           # Claude AI integration
│   │   ├── database.py                # Database models and connections
│   │   ├── ghl_client.py              # GoHighLevel API client
│   │   ├── monitoring.py              # Logging and performance monitoring
│   │   ├── rate_limiter.py            # API rate limiting utilities
│   │   ├── security.py                # Security middleware and validation
│   │   ├── email_client.py            # Email automation (SendGrid)
│   │   ├── sms_client.py              # SMS automation (Twilio)
│   │   └── config.py                  # Configuration management
│   │
│   ├── lead_bot/                      # 🔥 Lead qualification and nurturing
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app (Port 8001)
│   │   ├── intelligence.py            # Claude-powered lead analysis
│   │   ├── response_sequences.py      # Automated follow-up sequences
│   │   ├── ghl_handlers.py            # GHL webhook processors
│   │   ├── models.py                  # Lead-specific data models
│   │   ├── scoring.py                 # Lead scoring algorithms
│   │   ├── qualification.py           # Budget/timeline qualification
│   │   ├── nurturing.py               # Long-term nurture campaigns
│   │   └── analytics.py               # Lead performance analytics
│   │
│   ├── seller_bot/                    # 💰 CMA automation and pricing
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app (Port 8002)
│   │   ├── cma_engine.py              # CMA generation engine
│   │   ├── market_analysis.py         # Pricing strategy and market analysis
│   │   ├── zillow_client.py           # Property data integration
│   │   ├── pdf_generator.py           # CMA report PDF generation
│   │   ├── comparable_sales.py        # Comparable property analysis
│   │   ├── pricing_strategy.py        # AI-powered pricing recommendations
│   │   ├── marketing_automation.py    # Listing marketing campaigns
│   │   ├── listing_optimization.py    # Listing performance optimization
│   │   └── models.py                  # Seller-specific data models
│   │
│   └── buyer_bot/                     # 🏡 Property matching and learning
│       ├── __init__.py
│       ├── main.py                    # FastAPI app (Port 8003)
│       ├── matching_engine.py         # Property matching algorithm
│       ├── behavioral_learning.py     # Buyer preference learning
│       ├── property_client.py         # Property search integration
│       ├── showing_coordinator.py     # Appointment scheduling
│       ├── preference_tracker.py      # Buyer preference evolution
│       ├── psychological_analysis.py  # Buyer psychology analysis
│       ├── recommendation_engine.py   # Property recommendation system
│       └── models.py                  # Buyer-specific data models
```

---

## 🎛️ Command Center Structure

```
command_center/
├── __init__.py
├── main.py                           # Streamlit dashboard (Port 8501)
├── claude_concierge.py               # Omnipresent AI concierge
├── metrics_collector.py              # Cross-bot metrics aggregation
├── dashboard_components.py           # Reusable Streamlit components
├── cross_bot_intelligence.py         # Opportunity detection across bots
├── daily_briefing.py                 # Jorge's morning briefing generation
├── performance_tracking.py           # KPI tracking and analytics
├── client_timeline.py                # Client journey visualization
└── components/
    ├── lead_dashboard.py              # Lead-specific dashboard
    ├── seller_dashboard.py            # Seller-specific dashboard
    ├── buyer_dashboard.py             # Buyer-specific dashboard
    ├── analytics_dashboard.py         # Advanced analytics
    ├── chat_interface.py              # Claude chat interface
    └── mobile_components.py           # Mobile-responsive components
```

---

## 🔗 Integration Layer Structure

```
ghl_integration/
├── __init__.py
├── webhook_router.py                 # Central webhook routing
├── api_client.py                     # GHL API wrapper with rate limiting
├── custom_fields.py                  # Custom field management
├── pipeline_automation.py            # Pipeline stage automation
├── workflow_triggers.py              # GHL workflow integration
├── contact_management.py             # Contact CRUD operations
├── task_automation.py                # Automated task creation
└── models.py                         # GHL-specific data models

lyrio_integration/                    # Future platform integration
├── __init__.py
├── api_bridge.py                     # lyrio.io API integration
├── data_sync.py                      # Bi-directional data sync
├── widget_generator.py               # Embeddable widgets
└── platform_migration.py            # Migration utilities
```

---

## 🗄️ Database Structure

```
database/
├── models/                           # SQLAlchemy models
│   ├── __init__.py
│   ├── base.py                       # Base model class
│   ├── users.py                      # User/agent models (multi-tenant)
│   ├── contacts.py                   # Contact/lead models
│   ├── properties.py                 # Property data models
│   ├── interactions.py               # Client interaction tracking
│   ├── analytics.py                  # Analytics and metrics models
│   ├── bot_sessions.py               # Bot interaction sessions
│   └── audit_logs.py                 # Audit trail and compliance
│
├── migrations/                       # Alembic database migrations
│   ├── versions/                     # Migration files
│   └── env.py                        # Migration environment
│
└── seeds/                           # Sample/test data
    ├── jorge_sample_data.py          # Jorge's test leads/properties
    ├── test_contacts.py              # Test contact data
    └── demo_properties.py            # Demo property data
```

---

## 🧪 Testing Structure

```
tests/
├── __init__.py
├── conftest.py                       # Pytest configuration and fixtures
├── test_requirements.txt             # Testing dependencies
│
├── unit/                             # Fast unit tests
│   ├── test_lead_bot/
│   │   ├── test_intelligence.py      # Lead analysis unit tests
│   │   ├── test_scoring.py           # Lead scoring algorithm tests
│   │   └── test_ghl_handlers.py      # GHL integration unit tests
│   │
│   ├── test_seller_bot/
│   │   ├── test_cma_engine.py        # CMA generation unit tests
│   │   ├── test_pricing.py           # Pricing strategy tests
│   │   └── test_pdf_generation.py    # PDF report generation tests
│   │
│   ├── test_buyer_bot/
│   │   ├── test_matching.py          # Property matching tests
│   │   └── test_learning.py          # Behavioral learning tests
│   │
│   └── test_shared/
│       ├── test_claude_client.py     # Claude API integration tests
│       ├── test_ghl_client.py        # GHL client tests
│       └── test_database.py          # Database model tests
│
├── integration/                      # Cross-service integration tests
│   ├── test_lead_workflow.py         # End-to-end lead processing
│   ├── test_cma_workflow.py          # CMA generation workflow
│   ├── test_webhook_processing.py    # GHL webhook integration
│   └── test_cross_bot_features.py    # Cross-bot intelligence tests
│
├── e2e/                             # End-to-end tests
│   ├── test_jorge_daily_workflow.py  # Jorge's daily usage scenarios
│   ├── test_lead_to_close.py         # Complete lead lifecycle
│   └── test_performance.py           # Performance and load tests
│
└── fixtures/                        # Test data and mocks
    ├── sample_leads.json             # Sample lead data
    ├── sample_properties.json        # Sample property data
    ├── ghl_webhook_payloads.json     # Sample GHL webhooks
    └── mock_responses.py             # Mock API responses
```

---

## 📚 Documentation Structure

```
docs/
├── index.md                          # Documentation home
├── setup/                           # Setup and installation guides
│   ├── local_development.md         # Local dev environment setup
│   ├── ghl_setup.md                 # GoHighLevel configuration
│   ├── api_keys.md                  # API key acquisition guide
│   └── troubleshooting.md           # Common setup issues
│
├── user_guides/                     # User documentation
│   ├── jorge_daily_usage.md         # Jorge's daily workflow guide
│   ├── command_center_guide.md      # Dashboard usage instructions
│   ├── mobile_access.md             # Mobile usage guide
│   └── performance_optimization.md  # Getting best results
│
├── api/                             # API documentation
│   ├── lead_bot_api.md              # Lead Bot API reference
│   ├── seller_bot_api.md            # Seller Bot API reference
│   ├── buyer_bot_api.md             # Buyer Bot API reference
│   └── webhook_specifications.md    # Webhook payload specifications
│
├── deployment/                      # Deployment documentation
│   ├── staging_deployment.md        # Staging environment setup
│   ├── production_deployment.md     # Production deployment guide
│   ├── scaling_guide.md             # Horizontal scaling instructions
│   └── monitoring_setup.md          # Monitoring and alerting setup
│
└── architecture/                    # Technical architecture docs
    ├── system_design.md             # Overall system architecture
    ├── database_schema.md           # Database design documentation
    ├── security_architecture.md     # Security design and implementation
    └── performance_architecture.md  # Performance optimization guide
```

---

## ⚙️ Configuration Structure

```
config/
├── development.yaml                  # Development environment config
├── staging.yaml                     # Staging environment config
├── production.yaml                  # Production environment config
├── jorge_settings.yaml              # Jorge-specific business settings
├── api_rate_limits.yaml             # API rate limiting configuration
├── email_templates.yaml             # Email template definitions
├── sms_templates.yaml               # SMS template definitions
└── monitoring_config.yaml           # Monitoring and alerting config
```

---

## 🚀 Deployment Structure

```
deployment/
├── docker/
│   ├── Dockerfile                   # Production container definition
│   ├── docker-compose.yml           # Local development services
│   ├── docker-compose.staging.yml   # Staging environment
│   └── docker-compose.prod.yml      # Production environment
│
├── kubernetes/                      # Kubernetes manifests (future AWS)
│   ├── namespace.yaml
│   ├── deployments/
│   ├── services/
│   ├── configmaps/
│   └── secrets/
│
├── terraform/                       # Infrastructure as Code
│   ├── aws/                         # AWS infrastructure
│   ├── digitalocean/                # DigitalOcean setup
│   └── modules/                     # Reusable Terraform modules
│
├── scripts/
│   ├── deploy.sh                    # Deployment automation
│   ├── backup.sh                    # Database backup script
│   ├── restore.sh                   # Database restore script
│   ├── health_check.sh              # Health monitoring script
│   └── performance_test.sh          # Load testing script
│
└── monitoring/
    ├── datadog/                     # DataDog configuration
    ├── sentry/                      # Sentry error tracking setup
    ├── prometheus/                  # Prometheus metrics (future)
    └── grafana/                     # Grafana dashboards (future)
```

---

## 🔧 Development Tools Structure

```
.github/
├── workflows/
│   ├── ci.yml                       # Continuous Integration
│   ├── deploy-staging.yml           # Staging deployment
│   ├── deploy-production.yml        # Production deployment
│   └── security-scan.yml            # Security vulnerability scanning
│
├── ISSUE_TEMPLATE/
│   ├── bug_report.md                # Bug report template
│   ├── feature_request.md           # Feature request template
│   └── performance_issue.md         # Performance issue template
│
└── pull_request_template.md         # PR template with checklist

scripts/
├── setup_dev_env.sh                 # Development environment setup
├── run_tests.sh                     # Test execution script
├── code_quality_check.sh            # Linting and formatting
├── generate_api_docs.sh             # API documentation generation
└── create_migration.sh              # Database migration helper
```

---

## 📱 Mobile App Structure (Future)

```
mobile/                              # React Native mobile app (Phase 2)
├── src/
│   ├── components/                  # Reusable mobile components
│   ├── screens/                     # App screens
│   ├── navigation/                  # Navigation configuration
│   ├── services/                    # API integration
│   ├── store/                       # State management
│   └── utils/                       # Mobile utilities
│
├── android/                         # Android-specific files
├── ios/                            # iOS-specific files
├── package.json                     # Node.js dependencies
└── app.json                         # Expo configuration
```

---

## 🔐 Security Structure

```
security/
├── certificates/                    # SSL/TLS certificates
├── secrets/                        # Secret management (encrypted)
├── policies/                       # Security policies
│   ├── data_retention.md           # Data retention policy
│   ├── privacy_policy.md           # Privacy policy
│   └── security_policy.md          # Security policy
└── compliance/                     # Compliance documentation
    ├── gdpr_compliance.md           # GDPR compliance guide
    ├── ccpa_compliance.md           # CCPA compliance guide
    └── audit_procedures.md          # Security audit procedures
```

---

## 📊 Analytics Structure

```
analytics/
├── models/                          # Analytics data models
├── reports/                         # Automated report generation
├── dashboards/                      # Business intelligence dashboards
├── etl/                            # Data extraction, transformation, loading
└── ml_models/                       # Machine learning models (future)
    ├── lead_scoring.py              # Advanced lead scoring
    ├── price_prediction.py          # Property price prediction
    └── market_analysis.py           # Market trend analysis
```

---

## 🎯 Usage Patterns by File Type

### **Daily Development**
- `jorge_launcher.py` - Start all services
- `bots/*/main.py` - Individual bot FastAPI apps
- `command_center/main.py` - Dashboard interface
- `.env` - Environment configuration

### **GHL Integration**
- `ghl_integration/` - All GoHighLevel integration code
- `GHL_INTEGRATION.md` - Setup instructions
- `bots/*/ghl_handlers.py` - Webhook processors

### **Deployment**
- `DEPLOYMENT_GUIDE.md` - Complete deployment instructions
- `docker-compose.yml` - Local services
- `requirements.txt` - Python dependencies
- `.github/workflows/` - CI/CD automation

### **Documentation**
- `README.md` - Project overview
- `SPECIFICATION.md` - Complete technical spec
- `API_DOCUMENTATION.md` - All API endpoints
- `QUICK_START.md` - 30-minute setup guide

### **Development Workflow**
- `DEVELOPMENT_CHECKLIST.md` - Phase-by-phase tasks
- `tests/` - All testing code
- `alembic/` - Database migrations
- `scripts/` - Development automation

---

**This structure supports Jorge's platform from development through enterprise scale, with clear separation of concerns and modular architecture for easy maintenance and feature additions.**