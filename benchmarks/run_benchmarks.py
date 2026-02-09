"""Jorge Real Estate Bots Performance Benchmarks."""
import time
import random
import re
from pathlib import Path

random.seed(42)


def percentile(data, p):
    k = (len(data) - 1) * p / 100
    f = int(k)
    c = f + 1 if f + 1 < len(data) else f
    return data[f] + (k - f) * (data[c] - data[f])


# --- Synthetic data ---

BUYER_INTENTS = [
    re.compile(r"\b(buy|purchase|looking\s+for|interested\s+in)\b.*\b(home|house|property|condo)\b", re.I),
    re.compile(r"\b(budget|afford|price\s+range|pre-?approv)\b", re.I),
    re.compile(r"\b(mortgage|loan|financing|down\s+payment)\b", re.I),
    re.compile(r"\b(bedroom|bathroom|sqft|square\s+feet|garage)\b", re.I),
    re.compile(r"\b(school|commute|neighborhood|area|location)\b", re.I),
    re.compile(r"\b(open\s+house|showing|tour|visit)\b", re.I),
]

SELLER_INTENTS = [
    re.compile(r"\b(sell|selling|list|listing)\b.*\b(home|house|property)\b", re.I),
    re.compile(r"\b(home\s+worth|property\s+value|CMA|appraisal)\b", re.I),
    re.compile(r"\b(market\s+analysis|comp|comparable)\b", re.I),
    re.compile(r"\b(staging|repairs|renovation|upgrade)\b", re.I),
    re.compile(r"\b(agent\s+commission|closing\s+cost|net\s+proceed)\b", re.I),
]

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
    "Need help with home buying process",
    "Tell me about the neighborhood near Victoria Gardens",
    "What's the average price per square foot in Rancho?",
    "I want to schedule a showing for the house on Foothill",
    "My agent commission question - how much do you charge?",
    "I need comparable sales for my neighborhood",
    "Budget $450,000 for a condo downtown",
    "How long does it take to sell a house here?",
    "Looking for investment property with good rental yield",
] * 15  # 300 messages

TEMPERATURE_SIGNALS = {
    "hot": [
        re.compile(r"\bpre-?approv", re.I),
        re.compile(r"\bready\s+to\s+(buy|sell|move)\b", re.I),
        re.compile(r"\bthis\s+week(end)?\b", re.I),
        re.compile(r"\bASAP|urgently|immediately\b", re.I),
        re.compile(r"\boffer|contract\b", re.I),
    ],
    "warm": [
        re.compile(r"\binterested\b", re.I),
        re.compile(r"\bthinking\s+about\b", re.I),
        re.compile(r"\bnext\s+(month|few\s+months)\b", re.I),
        re.compile(r"\bbudget\b", re.I),
        re.compile(r"\bschool|commute\b", re.I),
    ],
    "cold": [
        re.compile(r"\bjust\s+(browsing|looking|curious)\b", re.I),
        re.compile(r"\bmaybe\s+someday\b", re.I),
        re.compile(r"\bnot\s+sure\b", re.I),
        re.compile(r"\bno\s+rush\b", re.I),
    ],
}


# --- Benchmarks ---

def benchmark_intent_matching():
    """Intent regex matching (buyer + seller patterns)."""
    all_patterns = BUYER_INTENTS + SELLER_INTENTS
    times = []
    for _ in range(500):
        start = time.perf_counter()
        results = []
        for msg in SAMPLE_MESSAGES:
            buyer_score = 0
            seller_score = 0
            for p in BUYER_INTENTS:
                if p.search(msg):
                    buyer_score += 1
            for p in SELLER_INTENTS:
                if p.search(msg):
                    seller_score += 1
            total = max(buyer_score + seller_score, 1)
            intent = "buyer" if buyer_score > seller_score else "seller" if seller_score > buyer_score else "general"
            confidence = max(buyer_score, seller_score) / len(BUYER_INTENTS)
            results.append({"intent": intent, "confidence": round(confidence, 3)})
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    times.sort()
    return {
        "op": "Intent Matching (300 msgs, 11 patterns)",
        "n": 500,
        "p50": round(percentile(times, 50), 4),
        "p95": round(percentile(times, 95), 4),
        "p99": round(percentile(times, 99), 4),
        "ops_sec": round(500 / (sum(times) / 1000), 1),
    }


def benchmark_temperature_scoring():
    """Lead temperature scoring (hot/warm/cold signals)."""
    times = []
    for _ in range(500):
        start = time.perf_counter()
        for msg in SAMPLE_MESSAGES:
            hot_hits = sum(1 for p in TEMPERATURE_SIGNALS["hot"] if p.search(msg))
            warm_hits = sum(1 for p in TEMPERATURE_SIGNALS["warm"] if p.search(msg))
            cold_hits = sum(1 for p in TEMPERATURE_SIGNALS["cold"] if p.search(msg))
            # Weighted score: hot=3, warm=2, cold=1 (inverted for coldness)
            raw_score = (hot_hits * 30 + warm_hits * 15 - cold_hits * 10)
            # Normalize to 0-100
            score = max(0, min(100, raw_score + 40))
            if score >= 80:
                tag = "Hot-Lead"
            elif score >= 40:
                tag = "Warm-Lead"
            else:
                tag = "Cold-Lead"
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    times.sort()
    return {
        "op": "Temperature Scoring (300 msgs, 14 signals)",
        "n": 500,
        "p50": round(percentile(times, 50), 4),
        "p95": round(percentile(times, 95), 4),
        "p99": round(percentile(times, 99), 4),
        "ops_sec": round(500 / (sum(times) / 1000), 1),
    }


def benchmark_handoff_decision():
    """Handoff decision logic with confidence threshold."""
    CONFIDENCE_THRESHOLD = 0.7
    times = []
    for _ in range(500):
        start = time.perf_counter()
        decisions = []
        for msg in SAMPLE_MESSAGES:
            best_direction = None
            best_confidence = 0.0
            for direction, patterns in HANDOFF_TRIGGERS.items():
                hits = sum(1 for p in patterns if p.search(msg))
                confidence = hits / len(patterns)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_direction = direction
            # Apply threshold and rate limiting simulation
            should_handoff = best_confidence >= CONFIDENCE_THRESHOLD
            # Circular prevention check (mock: check if same handoff in last 30 min)
            contact_id = hash(msg) % 1000
            recent_handoffs = {}  # mock empty history
            is_circular = contact_id in recent_handoffs
            final_decision = should_handoff and not is_circular
            decisions.append({
                "direction": best_direction,
                "confidence": round(best_confidence, 3),
                "handoff": final_decision,
            })
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    times.sort()
    return {
        "op": "Handoff Decision (300 msgs, 0.7 threshold)",
        "n": 500,
        "p50": round(percentile(times, 50), 4),
        "p95": round(percentile(times, 95), 4),
        "p99": round(percentile(times, 99), 4),
        "ops_sec": round(500 / (sum(times) / 1000), 1),
    }


def benchmark_conversation_routing():
    """Conversation routing: bot selection + context assembly."""
    BOTS = {
        "lead": {"priority": 1, "patterns": BUYER_INTENTS[:2] + SELLER_INTENTS[:2]},
        "buyer": {"priority": 2, "patterns": BUYER_INTENTS},
        "seller": {"priority": 3, "patterns": SELLER_INTENTS},
    }
    conversation_contexts = [
        {
            "contact_id": f"contact_{i}",
            "current_bot": random.choice(["lead", "buyer", "seller"]),
            "message_count": random.randint(1, 50),
            "last_active": time.time() - random.randint(0, 86400),
            "tags": random.sample(["Hot-Lead", "Warm-Lead", "Cold-Lead", "Pre-Approved", "First-Time-Buyer"], k=random.randint(1, 3)),
        }
        for i in range(100)
    ]
    times = []
    for _ in range(500):
        start = time.perf_counter()
        for ctx in conversation_contexts:
            msg = random.choice(SAMPLE_MESSAGES)
            # Score each bot
            bot_scores = {}
            for bot_name, bot_config in BOTS.items():
                score = 0
                for p in bot_config["patterns"]:
                    if p.search(msg):
                        score += 1
                # Boost if already assigned
                if ctx["current_bot"] == bot_name:
                    score += 2
                # Boost by message count (continuity)
                score += min(ctx["message_count"] / 20, 1)
                bot_scores[bot_name] = score
            # Route to highest-scoring bot
            selected = max(bot_scores, key=bot_scores.get)
            # Build routing decision
            route = {
                "selected_bot": selected,
                "score": round(bot_scores[selected], 2),
                "switch": selected != ctx["current_bot"],
                "contact": ctx["contact_id"],
            }
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    times.sort()
    return {
        "op": "Conversation Routing (100 contexts, 3 bots)",
        "n": 500,
        "p50": round(percentile(times, 50), 4),
        "p95": round(percentile(times, 95), 4),
        "p99": round(percentile(times, 99), 4),
        "ops_sec": round(500 / (sum(times) / 1000), 1),
    }


def main():
    results = []
    benchmarks = [
        benchmark_intent_matching,
        benchmark_temperature_scoring,
        benchmark_handoff_decision,
        benchmark_conversation_routing,
    ]
    for bench in benchmarks:
        print(f"Running {bench.__doc__.strip()}...")
        r = bench()
        results.append(r)
        print(f"  P50: {r['p50']}ms | P95: {r['p95']}ms | P99: {r['p99']}ms | {r['ops_sec']} ops/sec")

    out = Path(__file__).parent / "RESULTS.md"
    with open(out, "w") as f:
        f.write("# Jorge Real Estate Bots Benchmark Results\n\n")
        f.write(f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("| Operation | Iterations | P50 (ms) | P95 (ms) | P99 (ms) | Throughput |\n")
        f.write("|-----------|-----------|----------|----------|----------|------------|\n")
        for r in results:
            f.write(f"| {r['op']} | {r['n']:,} | {r['p50']} | {r['p95']} | {r['p99']} | {r['ops_sec']:,.0f} ops/sec |\n")
        f.write("\n> All benchmarks use synthetic data. No external services required.\n")
    print(f"\nResults: {out}")


if __name__ == "__main__":
    main()
