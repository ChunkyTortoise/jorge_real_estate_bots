# ADR 0001: Three Separate Bots Instead of One Unified Bot

**Status**: Accepted
**Date**: 2025-12-15
**Decision Makers**: Engineering team

## Context

Real estate leads have fundamentally different needs at different stages of the pipeline. A first-time website visitor asking "what's available in Rancho Cucamonga?" needs a completely different conversation flow than a pre-approved buyer ready to schedule showings, or a homeowner requesting a comparative market analysis.

A single unified bot would need to handle all three personas simultaneously, leading to:
- Bloated prompt templates trying to cover every scenario
- Confused conversation state when a lead transitions between stages
- Difficulty tuning scoring models (lead temperature vs. financial readiness vs. seller motivation)
- Monolithic codebase that's hard to test and deploy independently

## Decision

Implement three specialized bots, each with domain-specific prompts, scoring models, and conversation flows:

1. **Lead Bot** -- Handles initial contact, 5-minute SLA enforcement, Q0-Q4 qualification, and temperature scoring (Hot/Warm/Cold). Publishes temperature tags to GoHighLevel CRM.

2. **Buyer Bot** -- Manages buyer qualification with financial readiness assessment, pre-approval verification, budget analysis, and weighted property matching against database listings.

3. **Seller Bot** -- Runs structured confrontational qualification (Q1-Q4), generates comparative market analyses, provides pricing strategy recommendations, and calculates FRS (Financial Readiness Score) and PCS (Property Condition Score).

A shared `Handoff Service` manages transitions between bots when intent signals cross a 0.7 confidence threshold.

## Consequences

### Positive
- Each bot has focused, shorter prompts that produce higher quality responses
- Scoring models are tuned per domain (temperature vs. financial readiness vs. seller motivation)
- Independent testing: 279 tests organized by bot with clear boundaries
- Independent deployment: can update seller CMA logic without touching lead qualification
- Clearer conversation flows with no state confusion between personas

### Negative
- Requires a handoff service to manage cross-bot transitions
- Some shared infrastructure (GHL client, Claude client, cache) must be maintained in a common module
- Three separate FastAPI apps means three ports and more operational surface area
- Context must be serialized and transferred during handoffs

### Mitigations
- Shared module (`bots/shared/`) provides common clients, config, and utilities
- Docker Compose orchestrates all services with a single command
- Handoff service includes circular prevention and rate limiting to prevent thrashing
- Command Center dashboard provides unified visibility across all bots
