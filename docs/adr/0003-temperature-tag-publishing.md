# ADR 0003: Lead Temperature Scoring and GHL Tag Automation

**Status**: Accepted
**Date**: 2025-12-22
**Decision Makers**: Engineering team

## Context

GoHighLevel CRM workflows require real-time lead classification to trigger the right follow-up sequences. Human agents need to see at a glance which leads are ready to convert and which need nurturing. Without automated scoring:

- Agents manually tag leads, introducing inconsistency and delays
- Hot leads sit in the same queue as cold leads, missing the conversion window
- Nurture sequences fire generically instead of being tailored to lead temperature
- No audit trail of how a lead's temperature changed over time

## Decision

Implement a three-tier temperature scoring system with automatic GoHighLevel tag publishing:

### Scoring Tiers

| Lead Score | Temperature Tag | CRM Actions |
|------------|----------------|-------------|
| >= 80 | **Hot-Lead** | Priority workflow trigger, immediate agent notification, calendar booking prompt |
| 40-79 | **Warm-Lead** | Nurture sequence enrollment, follow-up reminder at 24/48/72 hours |
| < 40 | **Cold-Lead** | Educational content drip, periodic check-in at 7/14/30 days |

### Scoring Factors
- **Engagement signals**: Message count, response speed, question specificity
- **Recency**: Time since last interaction (decays over hours/days)
- **GHL tag count**: Existing tags indicating prior qualification or interest
- **Intent strength**: Buyer/seller signals detected by the intent decoder
- **Budget indicators**: Mentioned price ranges, pre-approval status

### Tag Publishing
- Tags are published to GoHighLevel via the enhanced GHL client in real time
- Previous temperature tags are removed before applying the new one (no stacking)
- Tag changes are logged with timestamp and score breakdown for audit
- Publishing failures are retried with exponential backoff (max 3 attempts)

## Consequences

### Positive
- Agents see lead priority instantly in the CRM dashboard
- Automated workflows trigger appropriate follow-up sequences per tier
- Consistent classification across all leads, removing human bias
- Full audit trail of temperature changes with scoring breakdowns
- GHL workflow automations can branch on temperature tags

### Negative
- Tag overwrites can cause notification fatigue if a lead oscillates between tiers
- Scoring model relies on engagement signals that may not capture offline interest
- Real-time publishing adds latency to each lead interaction (mitigated by async publishing)
- GHL API rate limits (10 req/s) constrain bulk re-scoring operations

### Mitigations
- Hysteresis buffer: a lead must cross the threshold by 5 points to change tier (e.g., a Warm lead at 79 doesn't become Hot until 85)
- Async tag publishing runs in background tasks, not blocking the conversation response
- Batch re-scoring operations respect GHL rate limits with configurable concurrency
- Score breakdown is stored alongside the tag for debugging and model improvement
