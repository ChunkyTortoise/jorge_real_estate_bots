# Jorge Real Estate Bots Benchmark Results

**Date**: 2026-02-09 03:36:41

| Operation | Iterations | P50 (ms) | P95 (ms) | P99 (ms) | Throughput |
|-----------|-----------|----------|----------|----------|------------|
| Intent Matching (300 msgs, 11 patterns) | 500 | 3.654 | 5.9957 | 12.0605 | 251 ops/sec |
| Temperature Scoring (300 msgs, 14 signals) | 500 | 2.9096 | 3.9372 | 4.5585 | 346 ops/sec |
| Handoff Decision (300 msgs, 0.7 threshold) | 500 | 1.5508 | 2.3235 | 2.8151 | 628 ops/sec |
| Conversation Routing (100 contexts, 3 bots) | 500 | 1.6221 | 2.9033 | 7.8426 | 530 ops/sec |

> All benchmarks use synthetic data. No external services required.
