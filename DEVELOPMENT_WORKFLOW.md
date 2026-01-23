# 🏗️ Jorge's Real Estate AI Bot Platform - Development Workflow

**Comprehensive development strategy with Claude Code optimization**

Created: January 23, 2026
Status: Ready for Implementation

---

## 🎯 **MASTER DEVELOPMENT WORKFLOW PROMPT**

```
You are the lead architect for Jorge's Real Estate AI Bot Platform - a research-validated system targeting +$24K monthly revenue through AI automation. You will build three specialized FastAPI microservices (Lead Bot, Seller Bot, Buyer Bot) with a unified Streamlit command center, integrated with GoHighLevel CRM.

CRITICAL SUCCESS FACTORS:
- 5-minute lead response rule (10x conversion multiplier) - NON-NEGOTIABLE
- Claude AI integration with 98.4% accuracy for real estate analysis
- <500ms lead analysis, <90s CMA generation, <30s property matching
- Native GoHighLevel integration via webhooks and API
- Path to $1M ARR through multi-tenant SaaS expansion

ARCHITECTURE OVERVIEW:
```
jorge_real_estate_bots/
├── bots/
│   ├── lead_bot/ (Port 8001) - Semantic analysis, 5-min response automation
│   ├── seller_bot/ (Port 8002) - CMA generation, pricing strategies
│   ├── buyer_bot/ (Port 8003) - Property matching, behavioral learning
│   └── shared/ - Claude client, GHL integration, database models
├── command_center/ (Port 8501) - Streamlit dashboard with Claude concierge
├── ghl_integration/ - Webhooks, custom fields, pipeline automation
└── jorge_launcher.py - Single-file startup
```

DEVELOPMENT PHASES:
Phase 1 (Months 1-3): Jorge validation + MVP (Focus: Lead Bot → Seller Bot → Buyer Bot)
Phase 2 (Months 4-6): Multi-tenant (3-5 agents), $500-1K monthly revenue
Phase 3 (Months 7-12): SaaS platform (50+ agents), $2K-5K monthly revenue

TECHNICAL STACK:
- FastAPI (8,500 req/sec vs Flask's 2,100)
- Claude 3.5 Sonnet (98.4% accuracy for real estate)
- PostgreSQL + Redis (async support, caching)
- Streamlit (Jorge-friendly dashboard)
- GoHighLevel webhooks (100 req/10sec, 200K/day)

PERFORMANCE REQUIREMENTS:
- Lead analysis: <500ms (enforced monitoring)
- 5-minute response: >99% compliance
- API uptime: 99.9% during business hours
- Lead qualification: >85% accuracy vs Jorge's manual assessment

When developing, prioritize the 5-minute response rule above all else - this single metric drives the 10x conversion multiplier and Jorge's $24K revenue increase.
```

---

## 🛠️ **CLAUDE CODE SKILLS & TOOLS SELECTION**

### **🔧 Essential Claude Code Skills**

#### **Core Development Skills**
```bash
# Primary skills for this project
/test-driven-development     # Critical for 80% coverage, FastAPI testing
/defense-in-depth           # Security for real estate data, webhook validation
/condition-based-waiting    # Async operations, webhook processing, Claude API
/web-artifacts-builder      # Streamlit dashboard components, responsive design
/frontend-design            # Command center UI/UX optimization for Jorge
```

**Usage Priority:**
1. **test-driven-development** - Use immediately for all bot development (RED-GREEN-REFACTOR)
2. **defense-in-depth** - Apply to webhook validation, API security, PII protection
3. **condition-based-waiting** - Essential for async Claude API calls, GHL webhooks
4. **frontend-design** - Command center development, Jorge-friendly interfaces
5. **web-artifacts-builder** - Streamlit component development, dashboard optimization

#### **Specialized Development Skills**
```bash
# Advanced development patterns
/api-design-patterns        # FastAPI microservices architecture
/microservices-architecture # Three-bot system design
/webhook-development        # GHL integration patterns
/database-optimization      # PostgreSQL performance tuning
/performance-monitoring     # 5-minute rule enforcement
```

#### **Real Estate Domain Skills**
```bash
# Custom skills for real estate development
/ghl-integration           # GoHighLevel setup and automation
/streamlit-component       # Dashboard component development
/real-estate-patterns      # Domain-specific development patterns
/jorge-workflow           # Jorge's specific business process automation
```

### **🤖 Specialized Agent Selection**

#### **Architecture & Planning Agents**
```bash
# Use for system design and feature planning
Task(
    subagent_type="Plan",
    description="Design microservices architecture for real estate bots",
    model="sonnet"  # Complex architectural decisions
)

Task(
    subagent_type="feature-dev:code-architect",
    description="Design Lead Bot 5-minute response architecture",
    model="sonnet"
)

Task(
    subagent_type="feature-dev:code-explorer",
    description="Analyze existing real estate codebase patterns",
    model="haiku"  # Quick exploration
)
```

#### **Code Quality & Review Agents**
```bash
# Proactive code quality enforcement
Task(
    subagent_type="pr-review-toolkit:code-reviewer",
    description="Review Lead Bot implementation for performance",
    model="sonnet"
)

Task(
    subagent_type="pr-review-toolkit:silent-failure-hunter",
    description="Check Claude API error handling patterns",
    model="sonnet"
)

Task(
    subagent_type="pr-review-toolkit:type-design-analyzer",
    description="Review real estate data models and types",
    model="sonnet"
)

Task(
    subagent_type="pr-review-toolkit:comment-analyzer",
    description="Validate API documentation completeness",
    model="haiku"
)
```

#### **Testing & Quality Assurance Agents**
```bash
# Comprehensive testing strategy
Task(
    subagent_type="pr-review-toolkit:pr-test-analyzer",
    description="Analyze test coverage for real estate bots",
    model="sonnet"
)

Task(
    subagent_type="agent-sdk-dev:agent-sdk-verifier-py",
    description="Validate bot architecture and patterns",
    model="haiku"
)
```

#### **Exploration & Research Agents**
```bash
# When you need to understand existing code or patterns
Task(
    subagent_type="Explore",
    description="Find existing lead qualification patterns in codebase",
    thoroughness="medium",
    model="haiku"
)

Task(
    subagent_type="Explore",
    description="Research GHL integration patterns and webhooks",
    thoroughness="very thorough",
    model="sonnet"
)
```

### **🔗 MCP Server Integration Strategy**

#### **Core MCP Servers for Real Estate Platform**

**1. Serena (Code Intelligence) - CRITICAL**
```python
# Configuration for large real estate codebase navigation
serena_config = {
    "server_name": "serena",
    "priority": "critical",
    "use_cases": [
        "Navigate FastAPI microservices architecture",
        "Search real estate domain logic and patterns",
        "Refactor Claude AI integration code",
        "Optimize database queries and models",
        "Find GHL webhook handling patterns"
    ],
    "settings": {
        "max_results": 50,
        "include_context": True,
        "search_scope": ["bots/", "ghl_integration/", "command_center/"]
    }
}
```

**2. Context7 (Documentation) - HIGH PRIORITY**
```python
# For real estate and integration API documentation
context7_config = {
    "server_name": "context7",
    "priority": "high",
    "libraries": [
        "fastapi",           # Core API framework
        "sqlalchemy",        # Database ORM
        "streamlit",         # Dashboard framework
        "anthropic",         # Claude AI integration
        "redis",             # Caching layer
        "postgresql",        # Database
        "gohighlevel-api",   # CRM integration
        "zillow-api",        # Property data
        "twilio",            # SMS automation
        "sendgrid"           # Email automation
    ],
    "usage_patterns": [
        "Look up FastAPI async patterns for webhook handling",
        "Find Streamlit caching best practices",
        "Research Anthropic API rate limiting",
        "GoHighLevel webhook specifications"
    ]
}
```

**3. Greptile (Code Review & Analysis) - HIGH PRIORITY**
```python
# For PR reviews and code intelligence
greptile_config = {
    "server_name": "greptile",
    "priority": "high",
    "features": [
        "Real estate bot code reviews",
        "GoHighLevel integration analysis",
        "Performance optimization reviews",
        "Security vulnerability scanning",
        "Cross-bot data flow analysis"
    ],
    "review_focus": [
        "5-minute response rule compliance",
        "Claude AI error handling",
        "GHL webhook security",
        "Database performance patterns"
    ]
}
```

**4. Claude in Chrome (Testing & Validation) - MEDIUM PRIORITY**
```python
# For GHL integration testing and validation
chrome_config = {
    "server_name": "claude-in-chrome",
    "priority": "medium",
    "use_cases": [
        "Test GoHighLevel webhook setup in browser",
        "Validate custom field creation workflows",
        "Test pipeline automation in GHL interface",
        "Debug real estate CRM integration flows",
        "Validate Streamlit dashboard in different browsers"
    ],
    "automation_scenarios": [
        "Create test contact in GHL → verify webhook fires",
        "Test CMA PDF generation and download",
        "Validate mobile dashboard responsiveness"
    ]
}
```

#### **Custom MCP Server Development**

**Real Estate Data MCP Server**
```python
# Custom MCP server for real estate APIs and data
real_estate_mcp = {
    "name": "real-estate-data",
    "description": "Custom MCP server for real estate APIs and domain logic",
    "tools": [
        {
            "name": "zillow_property_search",
            "description": "Search properties via Zillow API with caching"
        },
        {
            "name": "mls_comparable_analysis",
            "description": "Find comparable sales for CMA generation"
        },
        {
            "name": "market_trend_analysis",
            "description": "Analyze market trends for pricing strategy"
        },
        {
            "name": "property_valuation_ai",
            "description": "AI-powered property valuation with confidence scoring"
        },
        {
            "name": "ghl_webhook_validator",
            "description": "Validate and test GHL webhook payloads"
        }
    ],
    "integration": "Built into seller_bot for CMA generation",
    "data_sources": ["Zillow", "RentSpider", "MLS", "County Records"]
}
```

### **🪝 Hook Strategy for Automation**

#### **Critical Performance Hooks**

**1. Five-Minute Rule Enforcement Hook**
```python
# .claude/hooks/performance_monitor.py
"""Critical hook to enforce 5-minute lead response rule"""

import time
import asyncio
from typing import Dict, Any

class FiveMinuteRuleHook:
    """Enforces the 5-minute lead response rule - NON-NEGOTIABLE"""

    async def pre_tool_use(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor lead processing start time"""
        if "new-lead" in context.get("tool_name", "").lower():
            context["metadata"] = context.get("metadata", {})
            context["metadata"]["lead_start_time"] = time.time()

            # Alert if we're already close to limit
            session_duration = context.get("session_duration", 0)
            if session_duration > 240:  # 4 minutes
                return {
                    "allow": True,
                    "warning": "🚨 CRITICAL: Approaching 5-minute lead response limit! Current: {session_duration}s"
                }

        return {"allow": True}

    async def post_tool_use(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate response time compliance"""
        if "new-lead" in context.get("tool_name", "").lower():
            start_time = context.get("metadata", {}).get("lead_start_time")
            if start_time:
                duration = time.time() - start_time

                if duration > 300:  # 5 minutes - VIOLATION
                    return {
                        "alert": f"🚨 CRITICAL VIOLATION: Lead response took {duration:.1f}s > 5 minutes!",
                        "severity": "critical",
                        "action": "immediate_escalation"
                    }
                elif duration > 240:  # 4 minutes - WARNING
                    return {
                        "warning": f"⚠️ WARNING: Lead response took {duration:.1f}s (approaching limit)",
                        "severity": "high"
                    }
                else:
                    return {
                        "success": f"✅ Lead response time: {duration:.1f}s (within 5-minute rule)",
                        "performance_metric": duration
                    }

        return {"allow": True}
```

**2. API Security & Validation Hook**
```python
# .claude/hooks/real_estate_security.py
"""Security hooks for real estate platform"""

import re
from typing import Dict, Any, List

class RealEstateSecurityHook:
    """Enforce security patterns for real estate data"""

    SENSITIVE_PATTERNS = [
        r"ANTHROPIC_API_KEY\s*=\s*['\"][^'\"]+['\"]",
        r"GHL_API_KEY\s*=\s*['\"][^'\"]+['\"]",
        r"ZILLOW_API_KEY\s*=\s*['\"][^'\"]+['\"]",
        r"sk-[a-zA-Z0-9]+",  # API keys starting with sk-
        r"pk_[a-zA-Z0-9]+",  # Public keys starting with pk_
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN patterns
        r"\b\d{16}\b"  # Credit card patterns
    ]

    PII_PATTERNS = [
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email addresses
        r"\b\(\d{3}\)\s?\d{3}-\d{4}\b",  # Phone numbers
        r"\b\d{1,5}\s\w+\s(Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl)\b"  # Addresses
    ]

    async def pre_tool_use(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check for sensitive data before tool execution"""
        content = context.get("content", "")

        # Check for API keys in code
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return {
                    "allow": False,
                    "error": f"🔒 SECURITY VIOLATION: Sensitive data detected in code. Pattern: {pattern[:20]}..."
                }

        # Check for PII in logs or outputs
        if context.get("tool_name") in ["Write", "Edit"] and any("log" in context.get("file_path", "").lower() for _ in [1]):
            for pattern in self.PII_PATTERNS:
                if re.search(pattern, content):
                    return {
                        "allow": False,
                        "error": f"🔒 PII VIOLATION: Personal information detected in logs"
                    }

        return {"allow": True}

    async def validate_webhook_security(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate webhook signature verification is implemented"""
        content = context.get("content", "")

        if "webhook" in context.get("tool_name", "").lower():
            if "@app.post" in content and "webhook" in content:
                if not ("signature" in content and "verify" in content):
                    return {
                        "warning": "⚠️ Webhook endpoint missing signature verification",
                        "suggestion": "Add webhook signature validation for security"
                    }

        return {"allow": True}
```

**3. Jorge Business Rules Hook**
```python
# .claude/hooks/jorge_business_rules.py
"""Hooks for Jorge's specific business requirements"""

from typing import Dict, Any

class JorgeBusinessRulesHook:
    """Enforce Jorge's specific business rules and requirements"""

    JORGE_CONFIG = {
        "price_range": {"min": 200000, "max": 800000},
        "service_areas": ["Dallas", "Plano", "Frisco", "McKinney", "Allen"],
        "preferred_timeline": "60_days",
        "max_daily_leads": 50,
        "response_time_target": 300,  # 5 minutes
        "qualification_accuracy_target": 0.85
    }

    async def validate_lead_qualification(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure lead qualification follows Jorge's criteria"""
        content = context.get("content", "")

        if "lead_qualification" in content or "budget" in content:
            # Check for Jorge's price range validation
            if "200000" not in content or "800000" not in content:
                return {
                    "warning": f"💰 Consider Jorge's price range: ${self.JORGE_CONFIG['price_range']['min']:,}-${self.JORGE_CONFIG['price_range']['max']:,}",
                    "suggestion": "Add price range validation for Jorge's market"
                }

        return {"allow": True}

    async def validate_service_area(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure service area restrictions are applied"""
        content = context.get("content", "")

        if "location" in content or "area" in content:
            jorge_areas = self.JORGE_CONFIG["service_areas"]
            if not any(area in content for area in jorge_areas):
                return {
                    "info": f"🏡 Jorge's service areas: {', '.join(jorge_areas)}",
                    "suggestion": "Consider adding service area validation"
                }

        return {"allow": True}

    async def monitor_daily_limits(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor daily lead processing limits"""
        # This would integrate with actual metrics
        return {"allow": True}
```

**4. Performance Optimization Hook**
```python
# .claude/hooks/performance_optimization.py
"""Hooks for performance monitoring and optimization"""

import time
from typing import Dict, Any

class PerformanceOptimizationHook:
    """Monitor and optimize platform performance"""

    PERFORMANCE_TARGETS = {
        "lead_analysis_time": 0.5,      # 500ms
        "cma_generation_time": 90,       # 90 seconds
        "property_matching_time": 30,    # 30 seconds
        "api_response_time": 2.0,        # 2 seconds
        "database_query_time": 0.1       # 100ms
    }

    async def monitor_api_performance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor API endpoint performance"""
        tool_name = context.get("tool_name", "")
        start_time = context.get("start_time", time.time())

        if "claude" in tool_name.lower():
            # Monitor Claude API calls
            if time.time() - start_time > self.PERFORMANCE_TARGETS["lead_analysis_time"]:
                return {
                    "warning": f"⏱️ Claude API call slow: {time.time() - start_time:.2f}s > {self.PERFORMANCE_TARGETS['lead_analysis_time']}s target"
                }

        return {"allow": True}

    async def suggest_optimizations(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest performance optimizations based on patterns"""
        content = context.get("content", "")

        optimization_suggestions = []

        # Database optimization suggestions
        if "SELECT" in content and "WHERE" not in content:
            optimization_suggestions.append("Consider adding WHERE clause for database query optimization")

        # Caching suggestions
        if "api_call" in content and "cache" not in content:
            optimization_suggestions.append("Consider implementing caching for API calls")

        # Async suggestions
        if "requests.get" in content:
            optimization_suggestions.append("Consider using async HTTP client (httpx) for better performance")

        if optimization_suggestions:
            return {
                "suggestions": optimization_suggestions,
                "priority": "performance_optimization"
            }

        return {"allow": True}
```

### **🔌 Plugin Development Strategy**

#### **Core Real Estate Development Plugin**

**Plugin Structure:**
```python
# .claude/plugins/real-estate-dev/plugin.json
{
    "name": "real-estate-dev",
    "version": "1.0.0",
    "description": "Comprehensive real estate development tools and patterns for Jorge's platform",
    "author": "Jorge Real Estate Team",
    "commands": [
        "ghl-setup",
        "real-estate-test-data",
        "cma-template",
        "lead-scoring-test",
        "webhook-tester",
        "performance-benchmark",
        "jorge-config"
    ],
    "agents": [
        "real-estate-architect",
        "ghl-integration-specialist",
        "real-estate-tester",
        "performance-optimizer"
    ],
    "hooks": [
        "performance-monitor",
        "jorge-business-rules",
        "real-estate-security",
        "five-minute-rule-enforcer"
    ],
    "skills": [
        "ghl-integration",
        "real-estate-patterns",
        "jorge-workflow",
        "cma-generation"
    ]
}
```

#### **Command Implementations**

**1. GHL Setup Command**
```python
# .claude/plugins/real-estate-dev/commands/ghl-setup.md
---
description: Setup GoHighLevel integration for specified bot
usage: ghl-setup --bot=<lead|seller|buyer> --webhook=<webhook-type>
args:
  bot:
    description: Which bot to setup GHL integration for
    type: string
    required: true
    options: [lead, seller, buyer]
  webhook:
    description: Type of webhook to configure
    type: string
    required: true
    options: [new-contact, contact-response, listing-created]
---

# GoHighLevel Integration Setup

This command generates the necessary GHL integration code for the specified bot.

## Usage Examples

```bash
# Setup Lead Bot with new contact webhook
/ghl-setup --bot=lead --webhook=new-contact

# Setup Seller Bot with listing webhook
/ghl-setup --bot=seller --webhook=listing-created

# Setup comprehensive webhook testing
/ghl-setup --bot=lead --webhook=new-contact --include-tests=true
```

## Generated Files

- `bots/{bot}/ghl_handlers.py` - Webhook handlers
- `ghl_integration/{bot}_webhooks.py` - Webhook routing
- `tests/test_{bot}_ghl_integration.py` - Integration tests
- `config/{bot}_ghl_config.yaml` - Configuration

## GHL Custom Fields

The command will also generate the required custom fields configuration for your bot type.
```

**2. Real Estate Test Data Command**
```python
# .claude/plugins/real-estate-dev/commands/real-estate-test-data.md
---
description: Generate realistic test data for real estate platform development
usage: real-estate-test-data --type=<leads|properties|contacts> --count=<number>
args:
  type:
    description: Type of test data to generate
    type: string
    required: true
    options: [leads, properties, contacts, cmaSamples]
  count:
    description: Number of records to generate
    type: integer
    default: 10
  market:
    description: Real estate market to simulate
    type: string
    default: dallas
    options: [dallas, plano, frisco, austin, houston]
---

# Real Estate Test Data Generator

Generate realistic test data that matches Jorge's market and business patterns.

## Usage Examples

```bash
# Generate 50 realistic leads for Dallas market
/real-estate-test-data --type=leads --count=50 --market=dallas

# Generate properties in Jorge's price range
/real-estate-test-data --type=properties --count=100 --market=dallas --price-range=200000-800000

# Generate CMA test samples
/real-estate-test-data --type=cmaSamples --count=20 --market=dallas
```

## Generated Data Features

- **Realistic Names & Demographics**: Texas-appropriate names and demographics
- **Jorge's Price Range**: Properties in $200K-$800K range
- **Service Area Focus**: Dallas, Plano, Frisco, McKinney, Allen
- **Seasonal Patterns**: Reflects real estate market timing
- **Lead Quality Distribution**: Hot/Warm/Cold leads with realistic ratios
```

**3. CMA Template Command**
```python
# .claude/plugins/real-estate-dev/commands/cma-template.md
---
description: Generate CMA template and test pricing analysis
usage: cma-template --address=<property-address> --format=<pdf|json>
args:
  address:
    description: Property address for CMA generation
    type: string
    required: true
  format:
    description: Output format for CMA
    type: string
    default: pdf
    options: [pdf, json, html]
  accuracy-target:
    description: Target accuracy percentage for pricing
    type: integer
    default: 5
---

# CMA Template Generator

Generate Comparative Market Analysis templates and test pricing accuracy.

## Usage Examples

```bash
# Generate PDF CMA for specific property
/cma-template --address="123 Oak Street, Dallas, TX 75201" --format=pdf

# Generate JSON CMA data for testing
/cma-template --address="456 Main St, Plano TX" --format=json --accuracy-target=5

# Generate CMA with specific market conditions
/cma-template --address="789 Pine Ave, Frisco TX" --market-conditions=hot
```

## Features

- **Realistic Comparable Sales**: Based on actual market data patterns
- **AI-Powered Pricing Strategy**: Claude integration for pricing recommendations
- **Professional PDF Layout**: Jorge-branded CMA reports
- **Accuracy Validation**: Test against known sale prices
- **Market Trend Analysis**: Include current market conditions
```

#### **Agent Implementations**

**Real Estate Architect Agent**
```python
# .claude/plugins/real-estate-dev/agents/real-estate-architect.md
---
name: real-estate-architect
description: Specialized agent for designing real estate platform architecture
model: sonnet
color: blue
when_to_use: |
  Use when designing or reviewing real estate platform architecture, especially:
  - Microservices design for Lead/Seller/Buyer bots
  - Database schema for real estate data
  - Performance architecture for 5-minute response rule
  - Integration patterns with GHL and external APIs
tools: [Glob, Grep, Read, Write, Edit, NotebookEdit, WebFetch, WebSearch]
---

You are a specialized real estate platform architect with deep expertise in:

## Core Competencies
- **Real Estate Domain Knowledge**: Lead qualification, CMA generation, property matching
- **Performance Architecture**: Sub-5-minute response times, high-availability systems
- **Integration Patterns**: CRM integration, webhook design, API optimization
- **Data Architecture**: Real estate data models, search optimization, caching strategies

## Architecture Principles
1. **5-Minute Rule First**: All architecture decisions prioritize lead response time
2. **Jorge's Business Model**: Design for $200K-$800K property range, Dallas market
3. **Scale-Ready**: Architecture supports growth from 1 agent to 200+ agents
4. **Integration-Native**: Built for GoHighLevel and future lyrio.io integration

## Key Patterns
- FastAPI microservices with async processing
- Redis caching for sub-500ms responses
- PostgreSQL with real estate-optimized indexes
- Claude AI integration with error handling
- Webhook-driven architecture for real-time processing

When designing architecture, always include:
- Performance benchmarks and monitoring
- Error handling and fallback strategies
- Security considerations for PII and API keys
- Scaling considerations for multi-tenant growth
- Jorge's specific business requirements
```

### **🛠️ Development Utilities & Automation**

#### **Real Estate Development Utilities**
```python
# utils/real_estate_dev_utils.py
"""Comprehensive development utilities for real estate platform"""

import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class JorgeConfig:
    """Jorge's business configuration"""
    price_range = {"min": 200000, "max": 800000}
    service_areas = ["Dallas", "Plano", "Frisco", "McKinney", "Allen"]
    preferred_timeline = "60_days"
    commission_rate = 0.06
    target_monthly_leads = 100

class RealEstateTestDataGenerator:
    """Generate realistic test data for development"""

    def __init__(self, jorge_config: JorgeConfig):
        self.config = jorge_config
        self.dallas_streets = [
            "Oak Street", "Main Street", "Elm Avenue", "Pine Lane", "Maple Drive",
            "Cedar Court", "Birch Place", "Willow Way", "Cherry Hill", "Pecan Grove"
        ]
        self.buyer_names = [
            "Sarah Johnson", "Mike Davis", "Emily Rodriguez", "David Kim",
            "Jessica Smith", "Robert Taylor", "Amanda Wilson", "Chris Brown"
        ]

    def generate_leads(self, count: int = 50, market: str = "dallas") -> List[Dict]:
        """Generate realistic lead data"""
        leads = []

        for i in range(count):
            # Realistic lead quality distribution
            quality_roll = random.random()
            if quality_roll < 0.15:  # 15% hot leads
                temperature = "hot"
                score = random.randint(80, 100)
                timeline = random.choice(["ASAP", "30_days"])
            elif quality_roll < 0.35:  # 20% warm leads
                temperature = "warm"
                score = random.randint(60, 79)
                timeline = random.choice(["60_days", "90_days"])
            else:  # 65% cold leads
                temperature = "cold"
                score = random.randint(20, 59)
                timeline = random.choice(["90_days", "180_days", "exploring"])

            lead = {
                "id": f"lead_{i+1:04d}",
                "name": random.choice(self.buyer_names),
                "email": f"lead{i+1}@example.com",
                "phone": f"+1{random.randint(200, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}",
                "source": random.choice(["website", "facebook", "zillow", "referral", "google"]),
                "budget_min": random.randint(self.config.price_range["min"], self.config.price_range["max"] - 100000),
                "budget_max": random.randint(200000, self.config.price_range["max"]),
                "timeline": timeline,
                "ai_lead_score": score,
                "lead_temperature": temperature,
                "created_at": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
                "location_interest": random.choice(self.config.service_areas),
                "property_type": random.choice(["residential", "investment", "commercial"]),
                "financing_status": random.choice(["preapproved", "exploring", "not_started", "cash"])
            }

            # Add realistic messages based on quality
            if temperature == "hot":
                lead["initial_message"] = random.choice([
                    "I'm pre-approved and need to buy within 30 days",
                    "Cash buyer, looking in Plano area, when can we see properties?",
                    "Relocating for job, need home by end of month"
                ])
            elif temperature == "warm":
                lead["initial_message"] = random.choice([
                    "Looking to buy in the next few months",
                    "First time buyer, would like to learn about the process",
                    "Considering upgrading from current home"
                ])
            else:
                lead["initial_message"] = random.choice([
                    "Just browsing, might buy someday",
                    "What's the market like?",
                    "Thinking about maybe buying"
                ])

            leads.append(lead)

        return leads

    def generate_properties(self, count: int = 100, price_range: tuple = None) -> List[Dict]:
        """Generate realistic property data"""
        if not price_range:
            price_range = (self.config.price_range["min"], self.config.price_range["max"])

        properties = []

        for i in range(count):
            price = random.randint(price_range[0], price_range[1])
            bedrooms = random.choices([2, 3, 4, 5], weights=[10, 40, 35, 15])[0]
            bathrooms = random.choices([1.5, 2, 2.5, 3, 3.5], weights=[5, 25, 35, 25, 10])[0]
            sqft = random.randint(1200, 4500)

            property_data = {
                "id": f"prop_{i+1:04d}",
                "address": f"{random.randint(100, 9999)} {random.choice(self.dallas_streets)}",
                "city": random.choice(self.config.service_areas),
                "state": "TX",
                "zip_code": random.choice(["75201", "75024", "75034", "75070", "75013"]),
                "price": price,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "sqft": sqft,
                "lot_size": round(random.uniform(0.15, 0.8), 2),
                "year_built": random.randint(1995, 2023),
                "property_type": random.choice(["Single Family", "Townhouse", "Condo"]),
                "listing_date": (datetime.now() - timedelta(days=random.randint(1, 90))).isoformat(),
                "days_on_market": random.randint(1, 90),
                "price_per_sqft": round(price / sqft, 2),
                "features": random.sample([
                    "granite_countertops", "hardwood_floors", "stainless_appliances",
                    "fireplace", "pool", "garage", "updated_kitchen", "master_suite"
                ], k=random.randint(3, 6))
            }

            properties.append(property_data)

        return properties

    def generate_ghl_webhooks(self, lead_data: Dict) -> Dict:
        """Generate realistic GHL webhook payloads"""
        return {
            "eventType": "ContactCreate",
            "locationId": "jorge_location_123",
            "contact": {
                "id": lead_data["id"],
                "name": lead_data["name"],
                "email": lead_data["email"],
                "phone": lead_data["phone"],
                "source": lead_data["source"],
                "tags": ["lead", lead_data["lead_temperature"]],
                "customFields": {
                    "budget_min": lead_data["budget_min"],
                    "budget_max": lead_data["budget_max"],
                    "timeline": lead_data["timeline"]
                }
            },
            "timestamp": datetime.now().isoformat(),
            "signature": "mock_signature_for_testing"
        }

class PerformanceValidator:
    """Validate performance requirements for Jorge's platform"""

    def __init__(self):
        self.performance_targets = {
            "lead_analysis_time": 0.5,      # 500ms
            "five_minute_rule": 300,        # 5 minutes
            "cma_generation_time": 90,      # 90 seconds
            "property_matching_time": 30,   # 30 seconds
            "api_response_time": 2.0,       # 2 seconds
            "uptime_target": 0.999          # 99.9%
        }

    def validate_5_minute_rule(self, response_times: List[float]) -> Dict[str, Any]:
        """Ensure 99% compliance with 5-minute rule"""
        violations = [t for t in response_times if t > 300]
        compliance_rate = (len(response_times) - len(violations)) / len(response_times)

        return {
            "compliance_rate": compliance_rate,
            "target": 0.99,
            "passed": compliance_rate >= 0.99,
            "violations": len(violations),
            "max_response_time": max(response_times),
            "avg_response_time": sum(response_times) / len(response_times)
        }

    def validate_claude_response_time(self, api_calls: List[Dict]) -> Dict[str, Any]:
        """Ensure Claude API calls meet performance targets"""
        analysis_calls = [call for call in api_calls if call["type"] == "lead_analysis"]
        slow_calls = [call for call in analysis_calls if call["duration"] > 0.5]

        return {
            "total_calls": len(analysis_calls),
            "slow_calls": len(slow_calls),
            "performance_rate": (len(analysis_calls) - len(slow_calls)) / len(analysis_calls) if analysis_calls else 1.0,
            "avg_duration": sum(call["duration"] for call in analysis_calls) / len(analysis_calls) if analysis_calls else 0,
            "passed": len(slow_calls) / len(analysis_calls) < 0.05 if analysis_calls else True  # <5% slow calls
        }

class JorgeBusinessRuleValidator:
    """Validate Jorge's specific business rules"""

    def __init__(self, jorge_config: JorgeConfig):
        self.config = jorge_config

    def validate_lead_qualification(self, lead_data: Dict) -> Dict[str, Any]:
        """Validate lead meets Jorge's criteria"""
        issues = []

        # Check price range
        budget_min = lead_data.get("budget_min", 0)
        budget_max = lead_data.get("budget_max", 0)

        if budget_max < self.config.price_range["min"]:
            issues.append(f"Budget too low: ${budget_max:,} < ${self.config.price_range['min']:,}")

        if budget_min > self.config.price_range["max"]:
            issues.append(f"Budget too high: ${budget_min:,} > ${self.config.price_range['max']:,}")

        # Check service area
        location = lead_data.get("location_interest", "")
        if location and location not in self.config.service_areas:
            issues.append(f"Outside service area: {location}")

        # Check timeline reasonableness
        timeline = lead_data.get("timeline", "")
        if timeline in ["ASAP"] and lead_data.get("financing_status") == "not_started":
            issues.append("Unrealistic timeline: ASAP with no financing")

        return {
            "qualified": len(issues) == 0,
            "issues": issues,
            "confidence": max(0, 100 - len(issues) * 20)  # Confidence decreases with issues
        }

    def calculate_commission_potential(self, price: float) -> float:
        """Calculate Jorge's commission potential"""
        return price * self.config.commission_rate

    def validate_cma_accuracy(self, estimated_value: float, actual_sale_price: float) -> Dict[str, Any]:
        """Validate CMA pricing accuracy"""
        if actual_sale_price == 0:
            return {"error": "No sale price provided"}

        accuracy = abs(estimated_value - actual_sale_price) / actual_sale_price
        percentage_diff = accuracy * 100

        return {
            "estimated_value": estimated_value,
            "actual_sale_price": actual_sale_price,
            "accuracy_percentage": 100 - percentage_diff,
            "within_5_percent": percentage_diff <= 5,
            "within_10_percent": percentage_diff <= 10,
            "difference_amount": abs(estimated_value - actual_sale_price)
        }
```

---

## 🚀 **PHASE-BY-PHASE WORKFLOW IMPLEMENTATION**

### **Phase 1 Implementation (Months 1-3)**

#### **Month 1: Lead Bot Foundation**
```bash
# Week 1-2: Setup and Core Infrastructure
/test-driven-development --initialize-project --coverage-target=80

# Use Plan agent for architecture
Task(
    subagent_type="Plan",
    description="Design Lead Bot architecture with 5-minute response rule enforcement",
    model="sonnet"
)

# Enable critical hooks
# Performance monitoring hook (5-minute rule)
# Security validation hook
# Jorge business rules hook

# Activate MCP servers
# Serena: Code navigation and pattern search
# Context7: FastAPI, Claude AI, and Streamlit documentation
# Greptile: Code review and quality analysis

# Generate test data
/real-estate-test-data --type=leads --count=100 --market=dallas

# Week 3-4: Lead Bot Implementation
/ghl-setup --bot=lead --webhook=new-contact --include-tests=true

# Continuous testing with TDD
Task(
    subagent_type="pr-review-toolkit:pr-test-analyzer",
    description="Analyze test coverage for Lead Bot implementation"
)

# Performance validation
/performance-benchmark --target=lead-analysis --max-time=500ms
```

#### **Month 2: Seller Bot CMA Engine**
```bash
# CMA development with specialized testing
/cma-template --address="123 Oak St, Dallas TX" --format=pdf --accuracy-target=5

# Architecture review
Task(
    subagent_type="feature-dev:code-architect",
    description="Design CMA generation pipeline with <90s requirement"
)

# Security and quality review
Task(
    subagent_type="pr-review-toolkit:silent-failure-hunter",
    description="Check CMA generation error handling"
)

# Test with realistic data
/real-estate-test-data --type=properties --count=200 --market=dallas
```

#### **Month 3: Integration and Validation**
```bash
# Complete platform integration
Task(
    subagent_type="agent-sdk-dev:agent-sdk-verifier-py",
    description="Validate complete bot architecture and integration"
)

# Performance validation across all bots
/performance-benchmark --comprehensive --validate-5min-rule

# Jorge validation testing
/jorge-config --validate-business-rules --test-workflow
```

### **Continuous Quality Assurance**

#### **Pre-Commit Workflow**
```bash
# Automated quality checks before each commit
pre_commit_hooks = [
    "validate_5_minute_rule_compliance",
    "check_api_security_patterns",
    "validate_jorge_business_rules",
    "run_performance_benchmarks",
    "check_test_coverage"
]

# Example pre-commit validation
/test-driven-development --run-tests --coverage-check=80
Task(
    subagent_type="pr-review-toolkit:code-reviewer",
    description="Review changes for real estate platform standards"
)
```

#### **Daily Performance Monitoring**
```bash
# Daily automated checks
/performance-benchmark --daily-report --alert-on-violations
/webhook-tester --test-ghl-integration --validate-signatures
```

---

## 📊 **SUCCESS METRICS & VALIDATION**

### **Development Quality Metrics**
```python
success_metrics = {
    "code_coverage": {"target": 80, "critical": True},
    "lead_response_time": {"target": 300, "critical": True, "tolerance": 0.01},  # 99% compliance
    "claude_api_performance": {"target": 0.5, "critical": True},  # 500ms
    "cma_generation_time": {"target": 90, "critical": True},  # 90 seconds
    "test_automation": {"target": 100, "critical": True},  # All tests automated
    "jorge_satisfaction": {"target": 8.5, "critical": True}  # Out of 10
}
```

### **Hook Effectiveness Metrics**
```python
hook_metrics = {
    "five_minute_rule_enforcement": {"violations_caught": 0, "compliance_rate": 99.5},
    "api_security_detection": {"secrets_caught": 100, "pii_detection": 95},
    "business_rules_validation": {"jorge_rules_followed": 98},
    "performance_optimization": {"suggestions_implemented": 85}
}
```

### **MCP Server Utilization**
```python
mcp_utilization = {
    "serena": {"usage_rate": 75, "effectiveness": 90},  # Code navigation
    "context7": {"documentation_queries": 200, "accuracy": 95},  # API docs
    "greptile": {"code_reviews": 45, "issues_found": 120},  # Quality analysis
    "claude_in_chrome": {"integration_tests": 30, "success_rate": 98}  # GHL testing
}
```

---

## 🎯 **WORKFLOW OPTIMIZATION STRATEGIES**

### **Parallel Development Strategy**
```bash
# Use parallel agents for independent development
Task(subagent_type="feature-dev:code-architect", description="Design Lead Bot API", model="sonnet") &
Task(subagent_type="feature-dev:code-architect", description="Design Seller Bot CMA engine", model="sonnet") &
Task(subagent_type="pr-review-toolkit:type-design-analyzer", description="Review data models", model="haiku")

# Wait for completion, then integrate results
```

### **Context Management Strategy**
```python
# Optimize context usage with specialized MCP profiles
context_optimization = {
    "lead_bot_development": {
        "enabled_servers": ["serena", "context7"],
        "focus_areas": ["fastapi", "claude_ai", "webhook_handling"],
        "context_limit": 100000
    },
    "seller_bot_development": {
        "enabled_servers": ["serena", "context7", "real-estate-data"],
        "focus_areas": ["cma_generation", "pdf_creation", "zillow_api"],
        "context_limit": 120000
    },
    "integration_testing": {
        "enabled_servers": ["greptile", "claude-in-chrome"],
        "focus_areas": ["ghl_integration", "performance_testing"],
        "context_limit": 80000
    }
}
```

### **Performance-First Development**
```bash
# Every development action considers the 5-minute rule
development_principles = [
    "5-minute response rule takes priority over all other features",
    "Performance validation before feature completion",
    "Real-time monitoring during development",
    "Jorge's business rules integrated into all decisions",
    "Security and PII protection built-in, not added later"
]
```

---

**This comprehensive development workflow leverages Claude Code's complete ecosystem to efficiently build Jorge's Real Estate AI Bot Platform while maintaining the critical 5-minute response rule that drives the 10x conversion multiplier and $24K+ monthly revenue increase.**