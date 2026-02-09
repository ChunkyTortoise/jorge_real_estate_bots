# ADR 0002: 0.7 Confidence Threshold for Cross-Bot Handoff

**Status**: Accepted
**Date**: 2025-12-20
**Decision Makers**: Engineering team

## Context

With three specialized bots, leads sometimes express intent that belongs to a different bot. A lead asking "I want to buy a house with a $500K budget" in the Lead Bot should transition to the Buyer Bot. However:

- **Premature handoffs** frustrate users who get bounced between bots mid-conversation
- **Missed handoffs** lose qualified leads who never reach the right specialist
- **Rapid handoffs** can create loops (Lead -> Buyer -> Lead -> Buyer) when intent is ambiguous

We needed a threshold that balances precision (don't hand off unless confident) with recall (don't miss genuine transitions).

## Decision

Set a **0.7 confidence threshold** for cross-bot handoffs with the following safeguards:

### Confidence Scoring
- Intent decoder analyzes each message for cross-bot signals using regex pattern matching and semantic analysis
- Confidence score (0.0 - 1.0) reflects how strongly the message indicates a different bot is needed
- Threshold of 0.7 requires strong signal before triggering a handoff

### Trigger Phrases (examples)
| Direction | Phrases | Min Confidence |
|-----------|---------|---------------|
| Lead -> Buyer | "I want to buy", "budget $", "pre-approval" | 0.7 |
| Lead -> Seller | "sell my house", "home worth", "CMA" | 0.7 |
| Buyer -> Seller | "actually selling", "list my property" | 0.7 |

### Safeguards
- **Circular prevention**: Same source->target pair blocked within a 30-minute window
- **Rate limiting**: Maximum 3 handoffs per hour, 10 per day per contact
- **Conflict resolution**: Contact-level locking prevents concurrent handoff attempts
- **Pattern learning**: After accumulating 10+ outcome data points, the system dynamically adjusts thresholds based on historical success/failure rates

## Consequences

### Positive
- 0.7 threshold catches clear intent signals while ignoring casual mentions
- Circular prevention eliminates handoff loops
- Rate limiting prevents bot-thrashing for confused or adversarial users
- Pattern learning allows the system to self-tune over time
- All handoffs are logged with full context for audit and debugging

### Negative
- Some edge cases (confidence 0.6-0.7) may be missed, requiring the user to be more explicit
- Pattern learning requires minimum 10 data points before activating, so early behavior is static
- 30-minute circular prevention window may be too aggressive for legitimate back-and-forth scenarios

### Mitigations
- Bots prompt users with clarifying questions when confidence is in the 0.5-0.7 range
- Pattern learning minimum threshold prevents premature adjustments on insufficient data
- Circular prevention window is configurable per deployment
