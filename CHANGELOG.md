# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-09

### Added
- **Lead Bot** with semantic lead analysis, 5-minute SLA enforcement, Q0-Q4 qualification flow, and hot/warm/cold temperature scoring
- **Buyer Bot** with financial readiness assessment, pre-approval verification, budget analysis, and weighted property matching against PostgreSQL listings
- **Seller Bot** with confrontational Q1-Q4 qualification, comparative market analysis (CMA) generation, FRS/PCS scoring, and pricing strategy recommendations
- **Cross-Bot Handoff Service** with 0.7 confidence threshold, circular prevention (30-min window), rate limiting (3/hr, 10/day), contact-level locking, and pattern learning from outcomes
- **Intent Decoders** with regex and semantic analysis for lead, buyer, and seller intent detection, plus GHL-enhanced variants with tag boosts and engagement recency
- **Temperature Tag Publishing** to GoHighLevel CRM with three-tier scoring (Hot >= 80, Warm 40-79, Cold < 40) and automated workflow triggers
- **A/B Testing Service** with experiment management, deterministic variant assignment, and z-test statistical significance
- **Performance Tracker** with P50/P95/P99 latency tracking, SLA compliance monitoring, and rolling window analytics
- **Alerting Service** with configurable rules, cooldown periods, and 7 default alert rules
- **Bot Metrics Collector** with per-bot statistics, cache hit tracking, and alerting integration
- **Command Center** Streamlit dashboard with lead flow, bot performance, conversation health, and commission tracking
- **GoHighLevel Integration** with real-time CRM sync, webhook handlers, custom fields, and workflow triggers
- **Docker Compose** stack with PostgreSQL, Redis, 3 bot services, and dashboard
- **279 tests** covering all bots, shared services, command center, and integration scenarios
- Architecture Decision Records (ADRs) for three-bot separation, handoff thresholds, and temperature scoring
- Performance benchmarks for intent detection, temperature scoring, handoff decisions, and conversation routing
