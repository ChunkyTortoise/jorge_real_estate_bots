# Jorge Real Estate Bots -- Benchmarks

## Methodology

All benchmarks use **synthetic data only** -- no API keys, databases, or external services required. Measurements use `time.perf_counter()` for high-resolution timing. Each benchmark runs multiple iterations to compute P50/P95/P99 latencies.

## Benchmarks

### Bot Response Latency

Simulates the core response pipeline for each bot (Lead, Buyer, Seller):

1. **Intent matching** -- Regex pattern matching against buyer/seller intent signals
2. **Temperature scoring** -- Hot/Warm/Cold classification from conversation signals
3. **Response assembly** -- Template selection and variable substitution

| Bot | Target | What It Measures |
|-----|--------|-----------------|
| Lead Bot | <2000ms (P99) | Initial qualification and routing |
| Buyer Bot | <2000ms (P99) | Financial readiness + property matching |
| Seller Bot | <2000ms (P99) | CMA scoring + pricing strategy |

### Handoff Decision Overhead

Simulates the full cross-bot handoff evaluation:

1. **Confidence scoring** -- Pattern matching against handoff triggers (0.7 threshold)
2. **Circular prevention** -- Same source-to-target blocked within 30-minute window
3. **Rate limiting** -- 3 handoffs/hour, 10/day per contact

| Benchmark | Target | What It Measures |
|-----------|--------|-----------------|
| Handoff Decision | <50ms (P99) | End-to-end decision latency for 300 messages |

## Running

```bash
# Run all benchmarks
python benchmarks/run_all.py

# Run individual benchmarks
python benchmarks/bench_bot_response.py
python benchmarks/bench_handoff.py
```

## Notes

- Benchmarks measure **computation overhead only** -- actual production latency includes network I/O to Claude API, PostgreSQL, Redis, and GoHighLevel
- Results vary by machine. CI runs provide consistent baselines
- The existing `benchmarks/run_benchmarks.py` provides additional intent matching, temperature scoring, conversation routing, and throughput benchmarks
