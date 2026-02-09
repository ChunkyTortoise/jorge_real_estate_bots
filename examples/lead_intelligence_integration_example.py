"""
Example: Integrating Optimized Lead Intelligence with LeadAnalyzer

This example shows how to use the pattern-based lead intelligence
as a fallback when AI is unavailable or for ultra-fast scoring.

Author: Claude Code Assistant
Created: 2026-01-23
"""
from bots.shared.lead_intelligence_optimized import get_enhanced_lead_intelligence


def example_1_basic_usage():
    """Example 1: Basic usage of optimized lead intelligence"""
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Pattern-Based Scoring")
    print("="*60)

    message = "Looking for house in Plano around $500k. Pre-approved, need to move in 30 days."

    # Get analysis
    result = get_enhanced_lead_intelligence(message)

    print(f"\n📊 Lead Score: {result['lead_score']:.1f}/100")
    print(f"🔥 Urgency: {result['urgency']:.2f}")
    print(f"✅ Qualification: {result['qualification']:.2f}")
    print(f"💰 Budget: {result['budget_analysis']}")
    print(f"📅 Timeline: {result['timeline_analysis']}")
    print(f"📍 Locations: {', '.join(result['location_analysis'])}")
    print(f"💵 Financing: {result['financing_analysis']}")
    print(f"⚡ Fallback Used: {result['fallback_used']}")


def example_2_temperature_mapping():
    """Example 2: Map lead score to temperature (HOT/WARM/COLD)"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Score to Temperature Mapping")
    print("="*60)

    test_messages = [
        ("Cash buyer, $700k, Dallas, ASAP", "Expected: HOT"),
        ("Pre-approved, Plano, $400k, 60 days", "Expected: WARM"),
        ("Just browsing", "Expected: COLD")
    ]

    for message, expectation in test_messages:
        result = get_enhanced_lead_intelligence(message)
        score = result['lead_score']

        # Map score to temperature
        if score >= 80:
            temperature = "HOT 🔥"
        elif score >= 60:
            temperature = "WARM ☀️"
        else:
            temperature = "COLD ❄️"

        print(f"\n{expectation}")
        print(f"Message: \"{message}\"")
        print(f"Score: {score:.1f} → {temperature}")


def example_3_fallback_integration():
    """Example 3: Integration pattern with existing LeadAnalyzer"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Fallback Integration Pattern")
    print("="*60)

    print("\nPseudo-code for LeadAnalyzer integration:\n")
    print("""
class LeadAnalyzer:

    async def analyze_lead(self, lead_data, force_ai=False):
        metrics = PerformanceMetrics(start_time=time.time())

        try:
            # Try AI analysis first (existing logic)
            analysis = await self._analyze_with_ai(lead_data, metrics)

        except Exception as e:
            logger.warning(f"AI analysis failed: {e}, using pattern-based fallback")

            # Extract message from lead data
            message = self._extract_message_for_cache(lead_data)

            # Use optimized pattern-based scoring
            fallback = get_enhanced_lead_intelligence(message)

            # Convert to LeadAnalyzer format
            analysis = {
                "score": fallback["lead_score"],
                "temperature": self._score_to_temperature(fallback["lead_score"]),
                "reasoning": self._format_reasoning(fallback),
                "action": self._get_recommended_action(fallback),
                "budget_estimate": fallback.get("budget_max"),
                "timeline_estimate": fallback["timeline_analysis"],
                "fallback_used": True
            }

            metrics.analysis_type = "pattern_based"

        return analysis, metrics

    def _format_reasoning(self, fallback):
        parts = []
        if fallback["has_specific_budget"]:
            parts.append(f"{fallback['budget_analysis']} budget")
        if fallback["has_clear_timeline"]:
            parts.append(f"{fallback['timeline_analysis']} timeline")
        if fallback["has_location_preference"]:
            locations = ", ".join(fallback["location_analysis"])
            parts.append(f"interested in {locations}")

        return "Pattern-based: " + ", ".join(parts) if parts else "Pattern-based: minimal info"

    def _get_recommended_action(self, fallback):
        score = fallback["lead_score"]

        if score >= 80:
            return "Call immediately within 1 hour"
        elif score >= 60:
            return "Follow up within 24 hours"
        else:
            return "Add to nurture sequence"
    """)


def example_4_batch_processing():
    """Example 4: Batch processing multiple leads"""
    print("\n" + "="*60)
    print("EXAMPLE 4: Batch Processing Performance")
    print("="*60)

    import time

    leads = [
        "Pre-approved, $500k, Dallas, 30 days",
        "Cash buyer, $700k, Frisco",
        "Looking for house, maybe",
        "FHA loan, McKinney, $350k, 90 days",
        "Just browsing online"
    ]

    print(f"\nProcessing {len(leads)} leads...\n")

    start = time.time()
    results = []

    for i, message in enumerate(leads, 1):
        lead_start = time.time()
        result = get_enhanced_lead_intelligence(message)
        elapsed_ms = (time.time() - lead_start) * 1000

        results.append(result)

        # Determine temperature
        score = result['lead_score']
        if score >= 80:
            temp = "HOT 🔥"
        elif score >= 60:
            temp = "WARM ☀️"
        else:
            temp = "COLD ❄️"

        print(f"Lead {i}: {score:.1f} {temp} ({elapsed_ms:.2f}ms)")

    total_time = (time.time() - start) * 1000
    avg_time = total_time / len(leads)

    print(f"\nTotal: {total_time:.2f}ms")
    print(f"Average: {avg_time:.2f}ms per lead")
    print(f"Throughput: {len(leads) / (total_time/1000):.0f} leads/second")


def example_5_error_handling():
    """Example 5: Error handling and edge cases"""
    print("\n" + "="*60)
    print("EXAMPLE 5: Error Handling")
    print("="*60)

    edge_cases = [
        ("", "Empty message"),
        (None, "None message"),
        ("🏠 Looking for house 💰", "Unicode characters"),
        ("a" * 500, "Very long message"),
    ]

    for message, description in edge_cases:
        try:
            result = get_enhanced_lead_intelligence(message)
            print(f"\n{description}:")
            print(f"  Score: {result['lead_score']:.1f}")
            print(f"  Fallback Used: {result['fallback_used']}")
            if result['errors']:
                print(f"  Errors: {result['errors']}")
        except Exception as e:
            print(f"\n{description}: ERROR - {e}")


def example_6_real_world_scenarios():
    """Example 6: Real-world lead scenarios"""
    print("\n" + "="*60)
    print("EXAMPLE 6: Real-World Lead Scenarios")
    print("="*60)

    scenarios = [
        {
            "name": "Relocating Executive",
            "message": "Relocating to Dallas for work. Pre-approved for $750k conventional loan. Need to close by March 1st. Interested in Plano or Frisco."
        },
        {
            "name": "First-Time Buyer",
            "message": "First time buyer looking in McKinney. FHA loan, budget around $300k. Flexible timeline."
        },
        {
            "name": "Cash Investor",
            "message": "Cash buyer looking for investment properties in Dallas. Budget up to $500k. Can close quickly."
        },
        {
            "name": "Casual Browser",
            "message": "Just looking at options. Maybe someday."
        }
    ]

    for scenario in scenarios:
        result = get_enhanced_lead_intelligence(scenario["message"])
        score = result['lead_score']

        print(f"\n{scenario['name']}:")
        print(f"  Score: {score:.1f}/100")
        print(f"  Urgency: {result['urgency']:.2f}")
        print(f"  Qualification: {result['qualification']:.2f}")
        print(f"  Budget: {result['budget_analysis']}")
        print(f"  Timeline: {result['timeline_analysis']}")
        print(f"  Financing: {result['financing_analysis']}")


def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("LEAD INTELLIGENCE OPTIMIZED - INTEGRATION EXAMPLES")
    print("="*60)

    example_1_basic_usage()
    example_2_temperature_mapping()
    example_3_fallback_integration()
    example_4_batch_processing()
    example_5_error_handling()
    example_6_real_world_scenarios()

    print("\n" + "="*60)
    print("✅ ALL EXAMPLES COMPLETED")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
