# Jorge Real Estate Bots

**40% of real estate leads go cold because agents take >5 minutes to respond.** Three specialized bots handle lead qualification, buyer matching, and seller CMAs in real time.

[![CI](https://img.shields.io/github/actions/workflow/status/ChunkyTortoise/jorge_real_estate_bots/ci.yml?label=CI)](https://github.com/ChunkyTortoise/jorge_real_estate_bots/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-279_passing-brightgreen)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-F1C40F.svg)](LICENSE)

## What This Solves

- **Missed leads** -- Bots respond within seconds, not minutes. The Lead Bot enforces the 5-minute SLA and auto-qualifies prospects while human agents are busy
- **Manual qualification is slow** -- Structured Q0-Q4 question flows extract budget, timeline, pre-approval status, and motivation without agent involvement
- **No pipeline visibility** -- A Streamlit command center shows lead flow, bot performance, conversation health, and commission tracking across all three bots

## Architecture

```mermaid
flowchart LR
  subgraph Bots
    Lead["Lead Bot :8001"]
    Seller["Seller Bot :8002"]
    Buyer["Buyer Bot :8003"]
  end

  CommandCenter["Command Center :8501"]
  Postgres[(PostgreSQL)]
  Redis[(Redis)]
  Claude["Claude AI"]
  GHL["GoHighLevel"]

  Lead --> Redis
  Seller --> Redis
  Buyer --> Redis

  Lead --> Postgres
  Seller --> Postgres
  Buyer --> Postgres

  CommandCenter --> Postgres
  CommandCenter --> Redis

  Lead --> Claude
  Seller --> Claude
  Buyer --> Claude

  Lead --> GHL
  Seller --> GHL
  Buyer --> GHL
```

## Quick Start

```bash
git clone https://github.com/ChunkyTortoise/jorge_real_estate_bots.git
cd jorge_real_estate_bots
pip install -r requirements.txt

# Demo mode — no API keys needed, pre-seeded sample leads
python jorge_launcher.py --demo
```

### Full Setup (with external services)

```bash
cp .env.example .env
# Edit .env with your API keys

# Launch all services
python jorge_launcher.py

# Or launch individually
uvicorn bots.lead_bot.main:app --port 8001
uvicorn bots.seller_bot.main:app --port 8002
uvicorn bots.buyer_bot.main:app --port 8003
streamlit run command_center/dashboard_v3.py
```

## Bot Capabilities

**Lead Bot** -- Semantic lead analysis powered by Claude AI. Enforces the 5-minute response rule. Scores leads 0-100 with hot/warm/cold classification, triggers automated nurture sequences, and updates GoHighLevel CRM in real time.

**Seller Bot** -- Confrontational qualification engine using a structured Q1-Q4 question flow. Generates comparative market analyses, provides pricing strategy recommendations, and handles seller objections with configurable escalation paths.

**Buyer Bot** -- Full qualification flow (Q0-Q4), preference extraction, temperature scoring, and weighted property matching against Postgres listings. Writes buyer preferences and conversation history to the database and triggers GHL workflows when qualified.

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI, Pydantic, uvicorn |
| Dashboard | Streamlit, Plotly |
| AI | Claude (Haiku/Sonnet routing) |
| Database | PostgreSQL, SQLAlchemy (async), Alembic |
| Cache | Redis with in-memory fallback |
| CRM | GoHighLevel (webhooks, custom fields, workflows) |
| Testing | pytest, pytest-asyncio (279 tests) |

## Project Structure

```
jorge_real_estate_bots/
├── bots/
│   ├── shared/           # Config, Claude client, GHL client, cache, auth
│   ├── lead_bot/         # Semantic analysis, 5-min rule, webhook handlers
│   ├── seller_bot/       # Q1-Q4 qualification, CMA engine
│   └── buyer_bot/        # Buyer qualification + property matching
├── database/             # SQLAlchemy models, async session, repository
├── command_center/       # Streamlit dashboard + monitoring components
├── tests/                # 279 tests
├── jorge_launcher.py     # Single-command startup for all services
└── docker-compose.yml
```

## Testing

```bash
pytest tests/ -v                    # Full suite (279 tests)
pytest tests/shared/ -v             # Shared services
pytest tests/seller_bot/ -v         # Seller qualification
pytest tests/buyer_bot/ -v          # Buyer qualification
pytest tests/command_center/ -v     # Dashboard components
```

## Related Projects

- [EnterpriseHub](https://github.com/ChunkyTortoise/EnterpriseHub) -- Full real estate AI platform this was extracted from, with BI dashboards and CRM integration
- [ai-orchestrator](https://github.com/ChunkyTortoise/ai-orchestrator) -- AgentForge: unified async LLM interface (Claude, Gemini, OpenAI, Perplexity)
- [Revenue-Sprint](https://github.com/ChunkyTortoise/Revenue-Sprint) -- AI-powered freelance pipeline: job scanning, proposal generation, prompt injection testing

## License

MIT
