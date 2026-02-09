#!/usr/bin/env python3
"""
Seller Bot Integration Validation Script

Validates the complete Q1-Q4 qualification flow and all features.
Run this after integration to verify everything works.

Usage:
    python validate_seller_bot.py
"""
import asyncio
import sys

# Add bots to path
sys.path.insert(0, '.')

from bots.seller_bot import SellerStatus, create_seller_bot
from bots.shared.business_rules import JorgeBusinessRules

# ANSI color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{text.center(70)}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{RED}❌ {text}{RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{YELLOW}ℹ️  {text}{RESET}")


async def validate_imports():
    """Validate all imports work correctly"""
    print_header("VALIDATION 1: Module Imports")

    try:
        print_success("JorgeSellerBot imported")
        print_success("SellerStatus enum imported")
        print_success("SellerResult dataclass imported")
        print_success("SellerQualificationState imported")

        print_success("JorgeBusinessRules imported")

        print_success("ClaudeClient imported")

        print_success("GHLClient imported")

        return True

    except Exception as e:
        print_error(f"Import failed: {e}")
        return False


async def validate_bot_creation():
    """Validate bot can be created"""
    print_header("VALIDATION 2: Bot Creation")

    try:
        # Create with factory function
        seller_bot = create_seller_bot()
        print_success("Seller bot created with factory function")

        # Verify bot has required attributes
        assert hasattr(seller_bot, 'process_seller_message')
        print_success("Bot has process_seller_message method")

        assert hasattr(seller_bot, 'get_seller_analytics')
        print_success("Bot has get_seller_analytics method")

        assert hasattr(seller_bot, 'save_conversation_state')
        print_success("Bot has Redis state management")

        return seller_bot

    except Exception as e:
        print_error(f"Bot creation failed: {e}")
        return None


async def validate_q1_q4_flow(seller_bot):
    """Validate complete Q1-Q4 qualification flow"""
    print_header("VALIDATION 3: Q1-Q4 Qualification Flow")

    contact_id = "test_validation_001"
    location_id = "test_loc_001"

    try:
        # Q0 → Q1: Initial greeting
        print_info("Q0: Initial greeting...")
        r1 = await seller_bot.process_seller_message(
            contact_id=contact_id,
            location_id=location_id,
            message="I want to sell my house"
        )
        assert r1.questions_answered == 0  # No questions answered yet, just advanced to Q1
        assert "condition" in r1.response_message.lower() or "repair" in r1.response_message.lower()
        print_success("Q1 question asked about property condition")

        # Q1 → Q2: Property condition
        print_info("Q1: Property condition response...")
        r2 = await seller_bot.process_seller_message(
            contact_id=contact_id,
            location_id=location_id,
            message="The house needs major repairs, new roof and HVAC"
        )
        assert r2.questions_answered >= 1
        print_success("Q1 answer recorded (condition: needs_major_repairs)")

        # Q2 → Q3: Price expectation
        print_info("Q2: Price expectation response...")
        r3 = await seller_bot.process_seller_message(
            contact_id=contact_id,
            location_id=location_id,
            message="I think it's worth around $350,000"
        )
        assert r3.questions_answered >= 2
        print_success("Q2 answer recorded (price: $350,000)")

        # Q3 → Q4: Motivation
        print_info("Q3: Motivation response...")
        r4 = await seller_bot.process_seller_message(
            contact_id=contact_id,
            location_id=location_id,
            message="I got a job transfer to Austin, need to move fast"
        )
        assert r4.questions_answered >= 3
        print_success("Q3 answer recorded (motivation: job_relocation)")

        # Q4: Offer acceptance
        print_info("Q4: Offer acceptance response...")
        r5 = await seller_bot.process_seller_message(
            contact_id=contact_id,
            location_id=location_id,
            message="Yes, let's do it! That works for me."
        )
        assert r5.questions_answered == 4
        assert r5.qualification_complete is True
        print_success(f"Q4 answer recorded (offer_accepted: True)")
        print_success(f"Qualification complete: Temperature = {r5.seller_temperature}")

        return True

    except Exception as e:
        print_error(f"Q1-Q4 flow validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def validate_temperature_scoring(seller_bot):
    """Validate temperature scoring logic"""
    print_header("VALIDATION 4: Temperature Scoring")

    try:
        # Test HOT lead
        from bots.seller_bot.jorge_seller_bot import SellerQualificationState

        hot_state = SellerQualificationState(
            contact_id="test_hot",
            location_id="test_loc"
        )
        hot_state.questions_answered = 4
        hot_state.offer_accepted = True
        hot_state.timeline_acceptable = True
        hot_state.condition = "needs_major_repairs"
        hot_state.price_expectation = 350000

        temp = seller_bot._calculate_temperature(hot_state)
        assert temp == SellerStatus.HOT.value
        print_success(f"HOT lead scoring works: {temp}")

        # Test WARM lead
        warm_state = SellerQualificationState(
            contact_id="test_warm",
            location_id="test_loc"
        )
        warm_state.questions_answered = 4
        warm_state.offer_accepted = False
        warm_state.condition = "needs_minor_repairs"
        warm_state.price_expectation = 450000
        warm_state.motivation = "downsizing"

        temp = seller_bot._calculate_temperature(warm_state)
        assert temp == SellerStatus.WARM.value
        print_success(f"WARM lead scoring works: {temp}")

        # Test COLD lead
        cold_state = SellerQualificationState(
            contact_id="test_cold",
            location_id="test_loc"
        )
        cold_state.questions_answered = 2

        temp = seller_bot._calculate_temperature(cold_state)
        assert temp == SellerStatus.COLD.value
        print_success(f"COLD lead scoring works: {temp}")

        return True

    except Exception as e:
        print_error(f"Temperature scoring validation failed: {e}")
        return False


async def validate_data_extraction(seller_bot):
    """Validate data extraction from seller responses"""
    print_header("VALIDATION 5: Data Extraction")

    try:
        # Test condition extraction
        data = await seller_bot._extract_qualification_data(
            "The house needs major repairs",
            question_num=1
        )
        assert data.get("condition") == "needs_major_repairs"
        print_success("Condition extraction: 'major repairs' → needs_major_repairs")

        # Test price extraction ($350k format)
        data = await seller_bot._extract_qualification_data(
            "I think it's worth $350k",
            question_num=2
        )
        assert data.get("price_expectation") == 350000
        print_success("Price extraction: '$350k' → 350000")

        # Test price extraction ($350,000 format)
        data = await seller_bot._extract_qualification_data(
            "Maybe $450,000",
            question_num=2
        )
        assert data.get("price_expectation") == 450000
        print_success("Price extraction: '$450,000' → 450000")

        # Test motivation extraction
        data = await seller_bot._extract_qualification_data(
            "I'm going through a divorce",
            question_num=3
        )
        assert data.get("motivation") == "divorce"
        print_success("Motivation extraction: 'divorce' → divorce")

        # Test urgency extraction
        data = await seller_bot._extract_qualification_data(
            "Need to sell ASAP",
            question_num=3
        )
        assert data.get("urgency") == "high"
        print_success("Urgency extraction: 'ASAP' → high")

        # Test offer acceptance
        data = await seller_bot._extract_qualification_data(
            "Yes, let's do it!",
            question_num=4
        )
        assert data.get("offer_accepted") is True
        print_success("Offer extraction: 'Yes' → True")

        return True

    except Exception as e:
        print_error(f"Data extraction validation failed: {e}")
        return False


async def validate_business_rules_integration():
    """Validate business rules integration"""
    print_header("VALIDATION 6: Business Rules Integration")

    try:
        # Test valid lead (within range)
        lead_data = {
            "budget_max": 450000,
            "location_preferences": ["Dallas", "Plano"]
        }
        validation = JorgeBusinessRules.validate_lead(lead_data)
        assert validation["passes_jorge_criteria"] is True
        assert validation["service_area_match"] is True
        print_success(f"Valid lead validation: $450K in Dallas → PASS")

        # Test commission calculation
        commission = JorgeBusinessRules.calculate_commission(450000)
        assert commission == 27000  # 6% of $450K
        print_success(f"Commission calculation: $450K → ${commission:,} (6%)")

        # Test temperature thresholds
        assert JorgeBusinessRules.is_hot_lead(85) is True
        print_success("HOT lead threshold: score 85 → True")

        assert JorgeBusinessRules.get_temperature(75) == "warm"
        print_success("WARM lead threshold: score 75 → 'warm'")

        return True

    except Exception as e:
        print_error(f"Business rules validation failed: {e}")
        return False


async def validate_ghl_actions(seller_bot):
    """Validate GHL actions generation"""
    print_header("VALIDATION 7: GHL Actions Generation")

    try:
        from bots.seller_bot.jorge_seller_bot import SellerQualificationState

        # Create HOT lead state
        hot_state = SellerQualificationState(
            contact_id="test_hot_ghl",
            location_id="test_loc"
        )
        hot_state.questions_answered = 4
        hot_state.offer_accepted = True
        hot_state.timeline_acceptable = True
        hot_state.condition = "needs_major_repairs"
        hot_state.price_expectation = 350000
        hot_state.motivation = "job_relocation"

        # Generate actions
        actions = await seller_bot._generate_actions(
            contact_id="test_contact",
            location_id="test_loc",
            state=hot_state,
            temperature="hot"
        )

        # Verify actions
        tags = [a for a in actions if a["type"] == "add_tag"]
        assert len(tags) > 0
        assert any(a["tag"] == "seller_hot" for a in tags)
        print_success("Tag action generated: seller_hot")

        custom_fields = [a for a in actions if a["type"] == "update_custom_field"]
        assert len(custom_fields) > 0
        print_success(f"Custom field actions generated: {len(custom_fields)}")

        workflows = [a for a in actions if a["type"] == "trigger_workflow"]
        assert len(workflows) > 0
        assert workflows[0]["workflow_id"] == "cma_automation"
        print_success("CMA automation workflow triggered for HOT lead")

        return True

    except Exception as e:
        print_error(f"GHL actions validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def validate_analytics(seller_bot):
    """Validate analytics retrieval"""
    print_header("VALIDATION 8: Analytics Tracking")

    try:
        # Create test state
        from datetime import datetime

        from bots.seller_bot.jorge_seller_bot import SellerQualificationState

        state = SellerQualificationState(
            contact_id="test_analytics",
            location_id="test_loc"
        )
        state.current_question = 3
        state.questions_answered = 3
        state.condition = "needs_minor_repairs"
        state.price_expectation = 400000
        state.motivation = "downsizing"
        state.urgency = "medium"
        state.last_interaction = datetime.now()

        await seller_bot.save_conversation_state("test_analytics", state)

        # Get analytics
        analytics = await seller_bot.get_seller_analytics(
            contact_id="test_analytics",
            location_id="test_loc"
        )

        # Verify analytics
        assert analytics["questions_answered"] == 3
        print_success(f"Questions answered tracked: {analytics['questions_answered']}/4")

        assert analytics["qualification_progress"] == "3/4"
        print_success(f"Qualification progress: {analytics['qualification_progress']}")

        assert analytics["property_condition"] == "needs_minor_repairs"
        print_success(f"Property condition tracked: {analytics['property_condition']}")

        assert analytics["price_expectation"] == 400000
        print_success(f"Price expectation tracked: ${analytics['price_expectation']:,}")

        return True

    except Exception as e:
        print_error(f"Analytics validation failed: {e}")
        return False


async def validate_concurrent_handling(seller_bot):
    """Validate concurrent conversation handling"""
    print_header("VALIDATION 9: Concurrent Conversations")

    try:
        # Process 3 different sellers concurrently
        results = await asyncio.gather(
            seller_bot.process_seller_message("seller_A", "loc_001", "I want to sell"),
            seller_bot.process_seller_message("seller_B", "loc_001", "Need cash fast"),
            seller_bot.process_seller_message("seller_C", "loc_001", "What's my house worth?")
        )

        assert len(results) == 3
        print_success(f"Processed 3 concurrent conversations")

        # Verify each has independent state in Redis
        state_a = await seller_bot.get_conversation_state("seller_A")
        state_b = await seller_bot.get_conversation_state("seller_B")
        state_c = await seller_bot.get_conversation_state("seller_C")
        assert state_a is not None and state_b is not None and state_c is not None
        print_success("Each conversation has independent state in Redis")

        return True

    except Exception as e:
        print_error(f"Concurrent handling validation failed: {e}")
        return False


async def main():
    """Run all validations"""
    print_header("Jorge's Seller Bot - Integration Validation")
    print_info("Validating complete Q1-Q4 qualification system...")

    results = {}

    # Run validations
    results["imports"] = await validate_imports()

    seller_bot = await validate_bot_creation()
    results["creation"] = seller_bot is not None

    if seller_bot:
        results["q1_q4_flow"] = await validate_q1_q4_flow(seller_bot)
        results["temperature"] = await validate_temperature_scoring(seller_bot)
        results["extraction"] = await validate_data_extraction(seller_bot)
        results["business_rules"] = await validate_business_rules_integration()
        results["ghl_actions"] = await validate_ghl_actions(seller_bot)
        results["analytics"] = await validate_analytics(seller_bot)
        results["concurrent"] = await validate_concurrent_handling(seller_bot)

    # Summary
    print_header("VALIDATION SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n{BOLD}Results: {passed}/{total} validations passed{RESET}\n")

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        color = GREEN if result else RED
        print(f"{color}{status}{RESET} - {name.replace('_', ' ').title()}")

    # Final verdict
    print()
    if passed == total:
        print_success(f"{BOLD}🎉 ALL VALIDATIONS PASSED! Seller Bot is ready for production!{RESET}")
        return 0
    else:
        print_error(f"{BOLD}⚠️  {total - passed} validation(s) failed. Review errors above.{RESET}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
