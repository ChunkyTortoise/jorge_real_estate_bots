"""Benchmark: Bot response latency for Lead, Buyer, and Seller bots.

Simulates the core response pipeline (intent matching, scoring, response
assembly) using synthetic data. No API keys or external services required.

Target: <2000ms per bot response (P99).
"""
import random
import re
import time

random.seed(42)

ITERATIONS = 200


def percentile(data, p):
    k = (len(data) - 1) * p / 100
    f = int(k)
    c = f + 1 if f + 1 < len(data) else f
    return data[f] + (k - f) * (data[c] - data[f])


# --- Synthetic patterns ---

LEAD_PATTERNS = [
    re.compile(r"\b(hello|hi|hey|info|question)\b", re.I),
    re.compile(r"\b(interested|curious|tell\s+me)\b", re.I),
    re.compile(r"\b(market|area|neighborhood)\b", re.I),
    re.compile(r"\b(price|cost|afford)\b", re.I),
]

BUYER_PATTERNS = [
    re.compile(r"\b(buy|purchase|looking\s+for)\b.*\b(home|house|property|condo)\b", re.I),
    re.compile(r"\b(budget|pre-?approv|mortgage|loan)\b", re.I),
    re.compile(r"\b(bedroom|bathroom|sqft|garage)\b", re.I),
    re.compile(r"\b(school|commute|location)\b", re.I),
    re.compile(r"\b(open\s+house|showing|tour)\b", re.I),
]

SELLER_PATTERNS = [
    re.compile(r"\b(sell|listing|list)\b.*\b(home|house|property)\b", re.I),
    re.compile(r"\b(home\s+worth|CMA|appraisal|property\s+value)\b", re.I),
    re.compile(r"\b(comp|comparable|market\s+analysis)\b", re.I),
    re.compile(r"\b(staging|repairs|renovation)\b", re.I),
    re.compile(r"\b(commission|closing\s+cost|net\s+proceed)\b", re.I),
]

TEMPERATURE_SIGNALS = {
    "hot": [re.compile(r"\bpre-?approv", re.I), re.compile(r"\bready\s+to\b", re.I)],
    "warm": [re.compile(r"\binterested\b", re.I), re.compile(r"\bbudget\b", re.I)],
    "cold": [re.compile(r"\bjust\s+browsing\b", re.I), re.compile(r"\bnot\s+sure\b", re.I)],
}

SAMPLE_MESSAGES = [
    "I want to buy a home in Rancho Cucamonga with a budget of $500,000",
    "What's my home worth? I'm thinking about selling.",
    "Can you tell me about schools in the 91730 area?",
    "I have a pre-approval for $600K from Chase",
    "Sell my house - I need a CMA for 1234 Main St",
    "Looking for a 3 bedroom home with a garage",
    "Just browsing, what areas do you serve?",
    "Need help with the home buying process",
    "What's the average price per square foot here?",
    "My commission question - how much do you charge?",
]

RESPONSE_TEMPLATES = {
    "lead": [
        "Thanks for reaching out! I'd love to help you explore the {area} market.",
        "Great question! The {area} area has seen strong growth recently.",
        "Welcome! Let me gather some details to match you with the right specialist.",
    ],
    "buyer": [
        "Exciting! With a ${budget:,} budget, here are some options in {area}.",
        "Great news on the pre-approval! Let me pull up matching properties.",
        "I found {count} listings matching your {beds}bd/{baths}ba criteria.",
    ],
    "seller": [
        "I'd be happy to prepare a CMA for your property at {address}.",
        "Based on recent comps, homes in your area are selling for ${price:,}/sqft.",
        "Great timing - the {area} market favors sellers right now.",
    ],
}


def simulate_bot_response(bot_type, message):
    """Simulate a single bot response pipeline."""
    patterns = {"lead": LEAD_PATTERNS, "buyer": BUYER_PATTERNS, "seller": SELLER_PATTERNS}[bot_type]

    # Intent matching
    intent_score = sum(1 for p in patterns if p.search(message))
    confidence = intent_score / len(patterns)

    # Temperature scoring
    hot = sum(1 for p in TEMPERATURE_SIGNALS["hot"] if p.search(message))
    warm = sum(1 for p in TEMPERATURE_SIGNALS["warm"] if p.search(message))
    cold = sum(1 for p in TEMPERATURE_SIGNALS["cold"] if p.search(message))
    raw = hot * 30 + warm * 15 - cold * 10
    temp_score = max(0, min(100, raw + 40))
    tag = "Hot-Lead" if temp_score >= 80 else "Warm-Lead" if temp_score >= 40 else "Cold-Lead"

    # Response assembly
    template = random.choice(RESPONSE_TEMPLATES[bot_type])
    response = template.format(
        area="Rancho Cucamonga",
        budget=random.randint(300000, 800000),
        count=random.randint(3, 15),
        beds=random.randint(2, 5),
        baths=random.randint(1, 3),
        address="1234 Main St",
        price=random.randint(300, 600),
    )

    return {
        "response": response,
        "confidence": round(confidence, 3),
        "temperature": tag,
        "score": temp_score,
        "handoff_signals": intent_score > len(patterns) * 0.7,
    }


def run():
    """Run bot response benchmarks for all three bots."""
    results = {}
    target_ms = 2000

    for bot_type in ("lead", "buyer", "seller"):
        times = []
        for _ in range(ITERATIONS):
            start = time.perf_counter()
            for msg in SAMPLE_MESSAGES:
                simulate_bot_response(bot_type, msg)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)
        times.sort()
        p50 = round(percentile(times, 50), 4)
        p95 = round(percentile(times, 95), 4)
        p99 = round(percentile(times, 99), 4)
        passed = p99 < target_ms
        results[bot_type] = {
            "op": f"{bot_type.title()} Bot Response ({len(SAMPLE_MESSAGES)} msgs)",
            "n": ITERATIONS,
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "target": f"<{target_ms}ms",
            "passed": passed,
        }

    return results


if __name__ == "__main__":
    for bot, r in run().items():
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['op']}: P50={r['p50']}ms P95={r['p95']}ms P99={r['p99']}ms")
