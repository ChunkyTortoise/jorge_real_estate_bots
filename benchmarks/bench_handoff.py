"""Benchmark: Handoff decision time.

Simulates the full handoff decision pipeline: confidence scoring, circular
prevention check, and rate limit check. Uses synthetic data only.

Target: <50ms decision overhead (P99).
"""
import re
import time

ITERATIONS = 500
TARGET_MS = 50
CONFIDENCE_THRESHOLD = 0.7
RATE_LIMIT_HOURLY = 3
RATE_LIMIT_DAILY = 10
CIRCULAR_WINDOW_SEC = 1800  # 30 minutes


def percentile(data, p):
    k = (len(data) - 1) * p / 100
    f = int(k)
    c = f + 1 if f + 1 < len(data) else f
    return data[f] + (k - f) * (data[c] - data[f])


HANDOFF_TRIGGERS = {
    "lead_to_buyer": [
        re.compile(r"\bI\s+want\s+to\s+buy\b", re.I),
        re.compile(r"\bbudget\s+\$[\d,]+\b", re.I),
        re.compile(r"\bpre-?approv", re.I),
        re.compile(r"\blooking\s+for\s+a\s+(home|house|condo)\b", re.I),
    ],
    "lead_to_seller": [
        re.compile(r"\bsell\s+my\s+(home|house|property)\b", re.I),
        re.compile(r"\bhome\s+worth\b", re.I),
        re.compile(r"\bCMA\b", re.I),
        re.compile(r"\blist\s+my\s+(home|house|property)\b", re.I),
    ],
}

SAMPLE_MESSAGES = [
    "I want to buy a home in Rancho Cucamonga with a budget of $500,000",
    "What's my home worth? I'm thinking about selling.",
    "Can you tell me about schools in the 91730 area?",
    "I have a pre-approval for $600K from Chase",
    "Sell my house - I need a CMA for 1234 Main St",
    "Looking for a 3 bedroom home with a garage",
    "What are the mortgage rates right now?",
    "I want to list my property but need to know about staging",
    "How much are closing costs in California?",
    "I'm interested in the open house on Saturday",
    "Just browsing, what areas do you serve?",
    "Budget $450,000 for a condo downtown",
] * 25  # 300 messages


def evaluate_handoff(message, contact_id, handoff_history, hourly_counts, daily_counts):
    """Simulate full handoff evaluation pipeline."""
    # Step 1: Confidence scoring
    best_direction = None
    best_confidence = 0.0
    for direction, patterns in HANDOFF_TRIGGERS.items():
        hits = sum(1 for p in patterns if p.search(message))
        confidence = hits / len(patterns)
        if confidence > best_confidence:
            best_confidence = confidence
            best_direction = direction

    if best_confidence < CONFIDENCE_THRESHOLD:
        return {"handoff": False, "reason": "below_threshold"}

    # Step 2: Circular prevention check
    key = (contact_id, best_direction)
    if key in handoff_history:
        last_time = handoff_history[key]
        if (time.monotonic() - last_time) < CIRCULAR_WINDOW_SEC:
            return {"handoff": False, "reason": "circular_prevention"}

    # Step 3: Rate limit check
    hourly = hourly_counts.get(contact_id, 0)
    if hourly >= RATE_LIMIT_HOURLY:
        return {"handoff": False, "reason": "hourly_rate_limit"}

    daily = daily_counts.get(contact_id, 0)
    if daily >= RATE_LIMIT_DAILY:
        return {"handoff": False, "reason": "daily_rate_limit"}

    return {
        "handoff": True,
        "direction": best_direction,
        "confidence": round(best_confidence, 3),
    }


def run():
    """Run handoff decision benchmarks."""
    times = []
    handoff_history = {}
    hourly_counts = {}
    daily_counts = {}

    for _ in range(ITERATIONS):
        start = time.perf_counter()
        for i, msg in enumerate(SAMPLE_MESSAGES):
            contact_id = f"contact_{i % 50}"
            evaluate_handoff(msg, contact_id, handoff_history, hourly_counts, daily_counts)
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)

    times.sort()
    p50 = round(percentile(times, 50), 4)
    p95 = round(percentile(times, 95), 4)
    p99 = round(percentile(times, 99), 4)

    return {
        "handoff_decision": {
            "op": f"Handoff Decision ({len(SAMPLE_MESSAGES)} msgs, 0.7 threshold)",
            "n": ITERATIONS,
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "target": f"<{TARGET_MS}ms",
            "passed": p99 < TARGET_MS,
        }
    }


if __name__ == "__main__":
    for name, r in run().items():
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['op']}: P50={r['p50']}ms P95={r['p95']}ms P99={r['p99']}ms")
