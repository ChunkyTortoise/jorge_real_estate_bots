#!/usr/bin/env python3
"""Run all Jorge Real Estate Bots benchmarks and print summary."""
import sys
import os

# Ensure benchmarks package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.bench_bot_response import run as run_bot_response
from benchmarks.bench_handoff import run as run_handoff


def main():
    all_results = {}
    print("=" * 70)
    print("Jorge Real Estate Bots -- Performance Benchmarks")
    print("=" * 70)

    print("\n--- Bot Response Latency ---")
    bot_results = run_bot_response()
    all_results.update(bot_results)

    print("\n--- Handoff Decision Overhead ---")
    handoff_results = run_handoff()
    all_results.update(handoff_results)

    # Summary table
    print("\n" + "=" * 70)
    print(f"{'Benchmark':<50} {'P50':>8} {'P95':>8} {'P99':>8} {'Target':>10} {'Status':>8}")
    print("-" * 70)

    all_passed = True
    for name, r in all_results.items():
        status = "PASS" if r["passed"] else "FAIL"
        if not r["passed"]:
            all_passed = False
        print(f"{r['op']:<50} {r['p50']:>7.2f}ms {r['p95']:>7.2f}ms {r['p99']:>7.2f}ms {r['target']:>10} {status:>8}")

    print("=" * 70)
    if all_passed:
        print("All benchmarks PASSED.")
    else:
        print("Some benchmarks FAILED.")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
