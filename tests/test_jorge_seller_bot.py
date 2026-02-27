"""
Comprehensive tests for Jorge's Seller Bot.

Tests cover:
- Q1-Q4 qualification framework
- State machine conversation flow
- Temperature scoring (Hot/Warm/Cold)
- CMA automation triggers
- Jorge's confrontational tone preservation
- Business rules integration

Author: Claude Code Assistant
Created: 2026-01-23
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from bots.seller_bot.jorge_seller_bot import JorgeSellerBot, SellerQualificationState, SellerResult, SellerStatus
from bots.shared.business_rules import JorgeBusinessRules


class TestSellerQualificationState:
    """Test seller qualification state management"""

    def test_initial_state(self):
        """Test initial state is Q0_GREETING"""
        state = SellerQualificationState(
            contact_id="test_initial",
            location_id="loc_test"
        )
        assert state.current_question == 0
        assert state.questions_answered == 0
        assert state.is_qualified is False
        assert state.condition is None

    def test_advance_to_q1(self):
        """Test advancing from Q0 to Q1"""
        state = SellerQualificationState(
            contact_id="test_advance",
            location_id="loc_test"
        )
        state.advance_question()
        assert state.current_question == 1
        assert state.questions_answered == 0  # Not answered yet

    def test_record_q1_answer(self):
        """Test recording Q1 (condition) answer"""
        state = SellerQualificationState(
            contact_id="test_q1",
            location_id="loc_test"
        )
        state.advance_question()  # Move to Q1
        state.record_answer(
            question_num=1,
            answer="Needs major repairs",
            extracted_data={"condition": "needs_major_repairs"}
        )
        assert state.questions_answered == 1
        assert state.condition == "needs_major_repairs"

    def test_record_q2_answer(self):
        """Test recording Q2 (price expectation) answer"""
        state = SellerQualificationState(
            contact_id="test_q2",
            location_id="loc_test"
        )
        state.current_question = 2
        state.record_answer(
            question_num=2,
            answer="Around $350,000",
            extracted_data={"price_expectation": 350000}
        )
        assert state.questions_answered == 2
        assert state.price_expectation == 350000

    def test_record_q3_answer(self):
        """Test recording Q3 (motivation) answer"""
        state = SellerQualificationState(
            contact_id="test_q3",
            location_id="loc_test"
        )
        state.current_question = 3
        state.record_answer(
            question_num=3,
            answer="Job relocation to Austin",
            extracted_data={"motivation": "job_relocation", "urgency": "high"}
        )
        assert state.questions_answered == 3
        assert state.motivation == "job_relocation"

    def test_record_q4_answer_accepted(self):
        """Test recording Q4 (offer acceptance) - YES response"""
        state = SellerQualificationState(
            contact_id="test_q4_accept",
            location_id="loc_test"
        )
        state.current_question = 4
        state.record_answer(
            question_num=4,
            answer="Yes, that works for me",
            extracted_data={"offer_accepted": True, "timeline_acceptable": True}
        )
        assert state.questions_answered == 4
        assert state.offer_accepted is True
        assert state.timeline_acceptable is True
        assert state.is_qualified is True  # Should auto-mark as qualified

    def test_record_q4_answer_rejected(self):
        """Test recording Q4 (offer acceptance) - NO response"""
        state = SellerQualificationState(
            contact_id="test_q4_reject",
            location_id="loc_test"
        )
        state.current_question = 4
        state.record_answer(
            question_num=4,
            answer="No, I need more",
            extracted_data={"offer_accepted": False}
        )
        assert state.questions_answered == 4
        assert state.offer_accepted is False
        assert state.is_qualified is False

    def test_complete_qualification_flow(self):
        """Test complete Q1-Q4 qualification flow"""
        state = SellerQualificationState(
            contact_id="test_complete",
            location_id="loc_test"
        )

        # Q1: Condition
        state.advance_question()
        state.record_answer(1, "Minor repairs", {"condition": "needs_minor_repairs"})

        # Q2: Price expectation
        state.advance_question()
        state.record_answer(2, "$450,000", {"price_expectation": 450000})

        # Q3: Motivation
        state.advance_question()
        state.record_answer(3, "Divorce", {"motivation": "divorce", "urgency": "high"})

        # Q4: Offer acceptance
        state.advance_question()
        state.record_answer(4, "Yes", {"offer_accepted": True, "timeline_acceptable": True})

        assert state.questions_answered == 4
        assert state.is_qualified is True


class TestJorgeSellerBot:
    """Test Jorge's Seller Bot main functionality"""

    @pytest.fixture
    def mock_claude_client(self):
        """Mock Claude AI client"""
        from bots.shared.claude_client import LLMResponse
        client = AsyncMock()
        client.agenerate = AsyncMock(return_value=LLMResponse(
            content="Look, I'm not here to waste time. What condition is the house in?",
            model="claude-3-sonnet",
            input_tokens=100,
            output_tokens=50
        ))
        return client

    @pytest.fixture
    def mock_ghl_client(self):
        """Mock GHL client"""
        client = AsyncMock()
        client.add_tag = AsyncMock()
        client.update_custom_field = AsyncMock()
        return client

    @pytest.fixture
    def seller_bot(self, mock_claude_client, mock_ghl_client):
        """Create seller bot with mocked dependencies"""
        with patch('bots.seller_bot.jorge_seller_bot.ClaudeClient', return_value=mock_claude_client):
            bot = JorgeSellerBot(ghl_client=mock_ghl_client)
            return bot

    @pytest.mark.asyncio
    async def test_initial_greeting(self, seller_bot):
        """Test initial seller contact generates Q1"""
        result = await seller_bot.process_seller_message(
            contact_id="test_seller_001",
            location_id="loc_001",
            message="Hi, I want to sell my house",
            contact_info={"name": "John Smith"}
        )

        assert isinstance(result, SellerResult)
        assert result.response_message is not None
        # Q0 greeting asks Q1 but no answer has been recorded yet — questions_answered stays 0
        assert result.questions_answered == 0
        assert result.qualification_complete is False
        assert "condition" in result.response_message.lower() or "repair" in result.response_message.lower()

    @pytest.mark.asyncio
    async def test_q1_condition_response(self, seller_bot, mock_claude_client):
        """Test Q1 (condition) response processing"""
        # Mock Claude to return Q2 question
        from bots.shared.claude_client import LLMResponse
        mock_claude_client.agenerate = AsyncMock(return_value=LLMResponse(
            content="What do you REALISTICALLY think it's worth as-is?",
            model="claude-3-sonnet",
            input_tokens=100,
            output_tokens=50
        ))

        # First interaction - greeting
        await seller_bot.process_seller_message(
            contact_id="test_seller_002",
            location_id="loc_001",
            message="I want to sell"
        )

        # Second interaction - Q1 answer
        result = await seller_bot.process_seller_message(
            contact_id="test_seller_002",
            location_id="loc_001",
            message="The house needs major repairs, new roof and HVAC"
        )

        assert result.questions_answered >= 1
        # After answering Q1, should move to Q2 or show Q2-related content
        assert result.response_message is not None

    @pytest.mark.asyncio
    async def test_q2_price_response(self, seller_bot, mock_claude_client):
        """Test Q2 (price expectation) response processing"""
        from bots.shared.claude_client import LLMResponse
        mock_claude_client.agenerate = AsyncMock(return_value=LLMResponse(
            content="What's your real motivation? Job, financial, divorce?",
            model="claude-3-sonnet",
            input_tokens=100,
            output_tokens=50
        ))

        # Simulate Q2 state
        state = SellerQualificationState(
            contact_id="test_seller_003",
            location_id="loc_001"
        )
        state.current_question = 2
        state.questions_answered = 1
        await seller_bot.save_conversation_state("test_seller_003", state)

        result = await seller_bot.process_seller_message(
            contact_id="test_seller_003",
            location_id="loc_001",
            message="I think it's worth around $350,000"
        )

        assert result.questions_answered >= 2
        assert "motivation" in result.response_message.lower()

    @pytest.mark.asyncio
    async def test_q3_motivation_response(self, seller_bot, mock_claude_client):
        """Test Q3 (motivation) response processing"""
        from bots.shared.claude_client import LLMResponse
        mock_claude_client.agenerate = AsyncMock(return_value=LLMResponse(
            content="If I offer you $320,000 cash and close in 2-3 weeks, would you take it?",
            model="claude-3-sonnet",
            input_tokens=100,
            output_tokens=50
        ))

        # Simulate Q3 state
        state = SellerQualificationState(
            contact_id="test_seller_004",
            location_id="loc_001"
        )
        state.current_question = 3
        state.questions_answered = 2
        state.price_expectation = 350000
        await seller_bot.save_conversation_state("test_seller_004", state)

        result = await seller_bot.process_seller_message(
            contact_id="test_seller_004",
            location_id="loc_001",
            message="I got a job in Austin and need to move in 6 weeks"
        )

        assert result.questions_answered >= 3
        # Should contain offer or closing question
        assert "offer" in result.response_message.lower() or "close" in result.response_message.lower()

    @pytest.mark.asyncio
    async def test_q4_offer_accepted(self, seller_bot, mock_claude_client):
        """Test Q4 offer acceptance - HOT lead"""
        from bots.shared.claude_client import LLMResponse
        mock_claude_client.agenerate = AsyncMock(return_value=LLMResponse(
            content="Perfect! Let me get you scheduled with our team.",
            model="claude-3-sonnet",
            input_tokens=100,
            output_tokens=50
        ))

        # Simulate Q4 state with all previous answers
        state = SellerQualificationState(
            contact_id="test_seller_005",
            location_id="loc_001"
        )
        state.current_question = 4
        state.questions_answered = 3
        state.condition = "needs_minor_repairs"
        state.price_expectation = 350000
        state.motivation = "job_relocation"
        await seller_bot.save_conversation_state("test_seller_005", state)

        result = await seller_bot.process_seller_message(
            contact_id="test_seller_005",
            location_id="loc_001",
            message="Yes, that works for me. Let's do it."
        )

        assert result.questions_answered == 4
        assert result.qualification_complete is True
        assert result.seller_temperature == "hot"
        assert "actions_taken" in dir(result)

    @pytest.mark.asyncio
    async def test_q4_offer_rejected(self, seller_bot, mock_claude_client):
        """Test Q4 offer rejection - WARM/COLD lead"""
        from bots.shared.claude_client import LLMResponse
        mock_claude_client.agenerate = AsyncMock(return_value=LLMResponse(
            content="I understand. Let me follow up with you next week.",
            model="claude-3-sonnet",
            input_tokens=100,
            output_tokens=50
        ))

        # Simulate Q4 state
        state = SellerQualificationState(
            contact_id="test_seller_006",
            location_id="loc_001"
        )
        state.current_question = 4
        state.questions_answered = 3
        state.condition = "move_in_ready"
        state.price_expectation = 500000
        state.motivation = "testing_market"
        await seller_bot.save_conversation_state("test_seller_006", state)

        result = await seller_bot.process_seller_message(
            contact_id="test_seller_006",
            location_id="loc_001",
            message="No, I need to think about it"
        )

        assert result.questions_answered == 4
        assert result.qualification_complete is True
        assert result.seller_temperature in ["warm", "cold"]

    @pytest.mark.asyncio
    async def test_temperature_scoring_hot(self, seller_bot):
        """Test temperature scoring: HOT lead criteria"""
        state = SellerQualificationState(
            contact_id="test_hot",
            location_id="loc_test"
        )
        state.questions_answered = 4
        state.condition = "needs_major_repairs"
        state.price_expectation = 300000
        state.motivation = "foreclosure"
        state.offer_accepted = True
        state.timeline_acceptable = True

        temperature = seller_bot._calculate_temperature(state)
        assert temperature == SellerStatus.HOT.value

    @pytest.mark.asyncio
    async def test_temperature_scoring_warm(self, seller_bot):
        """Test temperature scoring: WARM lead criteria"""
        state = SellerQualificationState(
            contact_id="test_warm",
            location_id="loc_test"
        )
        state.questions_answered = 4
        state.condition = "needs_minor_repairs"
        state.price_expectation = 400000
        state.motivation = "downsizing"
        state.offer_accepted = False

        temperature = seller_bot._calculate_temperature(state)
        assert temperature == SellerStatus.WARM.value

    @pytest.mark.asyncio
    async def test_temperature_scoring_cold(self, seller_bot):
        """Test temperature scoring: COLD lead criteria"""
        state = SellerQualificationState(
            contact_id="test_cold",
            location_id="loc_test"
        )
        state.questions_answered = 2
        state.condition = "move_in_ready"
        state.price_expectation = 800000

        temperature = seller_bot._calculate_temperature(state)
        assert temperature == SellerStatus.COLD.value

    @pytest.mark.asyncio
    async def test_cma_automation_trigger(self, seller_bot, mock_ghl_client):
        """Test CMA automation triggers on qualification complete"""
        # Simulate complete qualification - HOT lead state
        state = SellerQualificationState(
            contact_id="test_seller_007",
            location_id="loc_001"
        )
        state.current_question = 4
        state.questions_answered = 4
        state.is_qualified = True
        state.condition = "needs_minor_repairs"
        state.price_expectation = 450000
        state.motivation = "job_relocation"
        state.offer_accepted = True
        state.timeline_acceptable = True  # This makes it HOT
        await seller_bot.save_conversation_state("test_seller_007", state)

        result = await seller_bot.process_seller_message(
            contact_id="test_seller_007",
            location_id="loc_001",
            message="Yes, let's move forward"
        )

        # Verify CMA automation was triggered for HOT lead
        assert result.seller_temperature == "hot", f"Expected hot, got {result.seller_temperature}"
        assert any(action.get("type") == "trigger_workflow" for action in result.actions_taken)

    @pytest.mark.asyncio
    async def test_ghl_actions_hot_lead(self, seller_bot, mock_ghl_client):
        """Test GHL actions applied for HOT lead"""
        state = SellerQualificationState(
            contact_id="test_seller_008",
            location_id="loc_001"
        )
        state.questions_answered = 4
        state.is_qualified = True
        state.offer_accepted = True
        state.timeline_acceptable = True
        await seller_bot.save_conversation_state("test_seller_008", state)

        result = await seller_bot.process_seller_message(
            contact_id="test_seller_008",
            location_id="loc_001",
            message="Yes, I accept"
        )

        # Verify actions
        actions = result.actions_taken
        assert any(action.get("tag") == "seller_hot" for action in actions if action.get("type") == "add_tag")
        assert any(action.get("field") == "seller_temperature" for action in actions if action.get("type") == "update_custom_field")

    @pytest.mark.asyncio
    async def test_confrontational_tone_preserved(self, seller_bot, mock_claude_client):
        """Test Jorge's confrontational tone is preserved"""
        from bots.shared.claude_client import LLMResponse
        mock_claude_client.agenerate = AsyncMock(return_value=LLMResponse(
            content="Look, I'm not here to waste time. What condition is the house in?",
            model="claude-3-sonnet",
            input_tokens=100,
            output_tokens=50
        ))

        result = await seller_bot.process_seller_message(
            contact_id="test_seller_009",
            location_id="loc_001",
            message="I want to sell"
        )

        # Check for Jorge's authentic phrases
        response_lower = result.response_message.lower()
        jorge_indicators = ["waste time", "straight", "serious", "truth", "runaround", "deal"]
        assert any(indicator in response_lower for indicator in jorge_indicators)

    @pytest.mark.asyncio
    async def test_analytics_tracking(self, seller_bot):
        """Test analytics are tracked throughout qualification"""
        state = SellerQualificationState(
            contact_id="test_seller_010",
            location_id="loc_001"
        )
        state.questions_answered = 3
        state.condition = "needs_major_repairs"
        state.price_expectation = 350000
        state.motivation = "divorce"
        await seller_bot.save_conversation_state("test_seller_010", state)

        analytics = await seller_bot.get_seller_analytics(
            contact_id="test_seller_010",
            location_id="loc_001"
        )

        assert analytics["questions_answered"] == 3
        assert analytics["qualification_progress"] == "3/4"
        assert analytics["qualification_complete"] is False
        assert analytics["property_condition"] == "needs_major_repairs"
        assert analytics["price_expectation"] == 350000

    @pytest.mark.asyncio
    async def test_error_handling_missing_contact(self, seller_bot):
        """Test graceful error handling for missing contact"""
        result = await seller_bot.process_seller_message(
            contact_id="nonexistent_seller",
            location_id="loc_001",
            message="Hello"
        )

        assert result is not None
        assert result.response_message is not None
        assert result.seller_temperature == "cold"

    @pytest.mark.asyncio
    async def test_business_rules_integration(self, seller_bot):
        """Test Jorge's business rules are applied"""
        # Should integrate with JorgeBusinessRules for validation
        state = SellerQualificationState(
            contact_id="test_business",
            location_id="loc_test"
        )
        state.price_expectation = 450000

        # This should pass Jorge's $200K-$800K range
        is_valid = JorgeBusinessRules.MIN_BUDGET <= state.price_expectation <= JorgeBusinessRules.MAX_BUDGET
        assert is_valid is True

    def test_seller_result_dataclass(self):
        """Test SellerResult dataclass structure"""
        result = SellerResult(
            response_message="Test message",
            seller_temperature="hot",
            questions_answered=4,
            qualification_complete=True,
            actions_taken=[{"type": "add_tag", "tag": "seller_hot"}],
            next_steps="Schedule consultation",
            analytics={"score": 95}
        )

        assert result.response_message == "Test message"
        assert result.seller_temperature == "hot"
        assert result.questions_answered == 4
        assert result.qualification_complete is True
        assert len(result.actions_taken) == 1


class TestSellerBotBugFixes:
    """Tests for the P0/P1 bug fixes (spec 2026-02-26)."""

    @pytest.fixture
    def mock_claude_client(self):
        from bots.shared.claude_client import LLMResponse
        client = AsyncMock()
        client.agenerate = AsyncMock(return_value=LLMResponse(
            content="What do you REALISTICALLY think it's worth as-is?",
            model="claude-haiku",
            input_tokens=10,
            output_tokens=5
        ))
        return client

    @pytest.fixture
    def mock_ghl_client(self):
        client = AsyncMock()
        client.add_tag = AsyncMock()
        client.remove_tag = AsyncMock()
        client.update_custom_field = AsyncMock()
        return client

    @pytest.fixture
    def seller_bot(self, mock_claude_client, mock_ghl_client):
        with patch('bots.seller_bot.jorge_seller_bot.ClaudeClient', return_value=mock_claude_client):
            return JorgeSellerBot(ghl_client=mock_ghl_client)

    # --- Fix 1: Q1 keyword expansion ---

    @pytest.mark.asyncio
    async def test_q1_okay_advances(self, seller_bot):
        """'it's okay' should extract condition and advance to Q2."""
        bot = seller_bot
        extracted = await bot._extract_qualification_data("it's okay", 1)
        assert "condition" in extracted
        assert extracted["condition"] != "unknown"

    @pytest.mark.asyncio
    async def test_q1_showing_its_age_advances(self, seller_bot):
        """'showing its age' should not leave condition unknown."""
        extracted = await seller_bot._extract_qualification_data("showing its age", 1)
        assert "condition" in extracted
        assert extracted["condition"] in ("needs_major_repairs", "needs_minor_repairs", "move_in_ready")

    @pytest.mark.asyncio
    async def test_q1_fast_path_still_works(self, seller_bot):
        """Fast-path keyword 'needs work' still maps to needs_major_repairs."""
        extracted = await seller_bot._extract_qualification_data("it needs major work", 1)
        assert extracted["condition"] == "needs_major_repairs"

    @pytest.mark.asyncio
    async def test_q1_should_advance_with_condition(self, seller_bot):
        """_should_advance_question Q1 returns True when condition is set."""
        assert seller_bot._should_advance_question({"condition": "needs_minor_repairs"}, 1) is True

    @pytest.mark.asyncio
    async def test_classify_with_claude_returns_default_on_failure(self, seller_bot, mock_claude_client):
        """_classify_with_claude returns default when API raises."""
        mock_claude_client.agenerate = AsyncMock(side_effect=Exception("API down"))
        result = await seller_bot._classify_with_claude(
            "some message", "classify it", ["a", "b", "c"], "b"
        )
        assert result == "b"

    # --- Fix 2: Q3 motivation expansion ---

    @pytest.mark.asyncio
    async def test_q3_retiring_advances(self, seller_bot):
        """'retiring' should set motivation and allow Q3 to advance."""
        extracted = await seller_bot._extract_qualification_data("I'm retiring and downsizing", 3)
        assert "motivation" in extracted
        assert extracted["motivation"] in ("retirement", "downsizing", "job_relocation",
                                           "financial_distress", "other")

    @pytest.mark.asyncio
    async def test_q3_tenant_problems_advances(self, seller_bot):
        """'tenant problems' should set motivation."""
        extracted = await seller_bot._extract_qualification_data("I have tenant problems", 3)
        assert "motivation" in extracted

    @pytest.mark.asyncio
    async def test_q3_should_advance_when_motivation_set(self, seller_bot):
        """_should_advance_question Q3 is True when motivation is present."""
        assert seller_bot._should_advance_question({"motivation": "retirement"}, 3) is True

    # --- Fix 6: Q4 offer/timeline separation ---

    @pytest.mark.asyncio
    async def test_q4_yes_sets_both_true(self, seller_bot):
        """'yes let's do it' → offer_accepted=True, timeline_acceptable=True."""
        extracted = await seller_bot._extract_qualification_data("yes let's do it", 4)
        assert extracted["offer_accepted"] is True
        assert extracted["timeline_acceptable"] is True

    @pytest.mark.asyncio
    async def test_q4_too_low_sets_both_false(self, seller_bot):
        """'too low' → offer_accepted=False, timeline_acceptable=False."""
        extracted = await seller_bot._extract_qualification_data("that's too low for me", 4)
        assert extracted["offer_accepted"] is False
        assert extracted["timeline_acceptable"] is False

    @pytest.mark.asyncio
    async def test_q4_timeline_pushback_independent(self, seller_bot):
        """'price is fine but need more time' → offer not rejected, timeline False."""
        extracted = await seller_bot._extract_qualification_data(
            "okay price is fine but I need more time to close", 4
        )
        # offer_accepted may be True (fine/okay), but timeline should be False
        assert extracted["timeline_acceptable"] is False

    # --- Fix 8: Tag cleanup ---

    @pytest.mark.asyncio
    async def test_generate_actions_removes_stale_tags(self, seller_bot):
        """When temperature=hot, remove_tag actions for warm and cold are present."""
        state = SellerQualificationState(
            contact_id="tag_test", location_id="loc1",
            questions_answered=4, offer_accepted=True, timeline_acceptable=True
        )
        state.condition = "move_in_ready"
        actions = await seller_bot._generate_actions("tag_test", "loc1", state, "hot")
        remove_tags = {a["tag"] for a in actions if a.get("type") == "remove_tag"}
        assert "seller_warm" in remove_tags
        assert "seller_cold" in remove_tags
        add_tags = {a["tag"] for a in actions if a.get("type") == "add_tag"}
        assert "seller_hot" in add_tags


class TestSellerBotEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.fixture
    def mock_claude_client(self):
        """Mock Claude AI client for edge case testing"""
        from bots.shared.claude_client import LLMResponse
        client = AsyncMock()
        client.agenerate = AsyncMock(return_value=LLMResponse(
            content="What condition is the house in?",
            model="claude-3-sonnet",
            input_tokens=100,
            output_tokens=50
        ))
        return client

    @pytest.fixture
    def mock_ghl_client(self):
        """Mock GHL client for edge case testing"""
        client = AsyncMock()
        client.add_tag = AsyncMock()
        client.update_custom_field = AsyncMock()
        return client

    @pytest.fixture
    def seller_bot(self, mock_claude_client, mock_ghl_client):
        """Create seller bot for edge case testing"""
        with patch('bots.seller_bot.jorge_seller_bot.ClaudeClient', return_value=mock_claude_client):
            bot = JorgeSellerBot(ghl_client=mock_ghl_client)
            return bot

    @pytest.mark.asyncio
    async def test_out_of_order_responses(self, seller_bot):
        """Test handling out-of-order qualification responses"""
        # User jumps ahead without answering previous questions
        result = await seller_bot.process_seller_message(
            contact_id="test_edge_001",
            location_id="loc_001",
            message="I accept your offer!"  # Jumping to Q4 without Q1-Q3
        )

        # Should handle gracefully and guide back to proper sequence
        assert result is not None

    @pytest.mark.asyncio
    async def test_ambiguous_responses(self, seller_bot):
        """Test handling ambiguous or unclear responses"""
        result = await seller_bot.process_seller_message(
            contact_id="test_edge_002",
            location_id="loc_001",
            message="Maybe, I don't know"
        )

        # Should prompt for clarification
        assert result is not None

    @pytest.mark.asyncio
    async def test_extremely_high_price_expectation(self, seller_bot):
        """Test handling price expectations above Jorge's range"""
        state = SellerQualificationState(
            contact_id="test_edge_003",
            location_id="loc_001"
        )
        state.current_question = 2
        await seller_bot.save_conversation_state("test_edge_003", state)

        result = await seller_bot.process_seller_message(
            contact_id="test_edge_003",
            location_id="loc_001",
            message="The house is worth $2 million"
        )

        # Should handle and mark as requiring review
        assert result is not None

    @pytest.mark.asyncio
    async def test_concurrent_conversations(self, seller_bot):
        """Test handling multiple concurrent seller conversations"""
        # Process messages from 3 different sellers simultaneously
        results = await asyncio.gather(
            seller_bot.process_seller_message("seller_A", "loc_001", "I want to sell"),
            seller_bot.process_seller_message("seller_B", "loc_001", "Need to sell fast"),
            seller_bot.process_seller_message("seller_C", "loc_001", "Interested in cash offer")
        )

        # All should be processed independently
        assert len(results) == 3
        assert all(r is not None for r in results)


class TestSellerBotEvalFixes:
    """Tests for evaluation-identified fixes: Q2 price fallback, history format."""

    @pytest.fixture
    def bot(self):
        return JorgeSellerBot()

    # --- Fix: Seller Q2 text-only price advances ---

    @pytest.mark.asyncio
    async def test_q2_numeric_price_still_works(self, bot):
        """$350k still extracts correctly via regex fast path."""
        extracted = await bot._extract_qualification_data("I think it's worth $350k", 2)
        assert extracted.get("price_expectation") == 350000

    @pytest.mark.asyncio
    async def test_q2_text_price_sets_default_on_haiku_failure(self, bot):
        """When Haiku fails, Q2 defaults to 300000 so conversation always advances."""
        from unittest.mock import AsyncMock, patch
        with patch.object(bot.claude_client, "agenerate", side_effect=Exception("API down")):
            extracted = await bot._extract_qualification_data("around three fifty", 2)
        assert "price_expectation" in extracted
        assert extracted["price_expectation"] == 300000

    @pytest.mark.asyncio
    async def test_q2_should_advance_with_default_price(self, bot):
        """_should_advance_question returns True when price_expectation set to default."""
        extracted = {"price_expectation": 300000}
        assert bot._should_advance_question(extracted, 2) is True

    # --- Fix: Seller history format ---

    def test_record_answer_stores_bot_response_field(self, bot):
        """record_answer initializes bot_response as empty string."""
        from bots.seller_bot.jorge_seller_bot import SellerQualificationState
        state = SellerQualificationState(contact_id="c1", location_id="loc1")
        state.record_answer(1, "needs work", {"condition": "needs_major_repairs"})
        assert "bot_response" in state.conversation_history[-1]
        assert state.conversation_history[-1]["bot_response"] == ""


# ─── Fix 2: Q0 message preserved ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seller_q0_message_preserved_in_history():
    """Initial Q0 message is appended to conversation_history before advancing."""
    from bots.shared.cache_service import get_cache_service

    bot = JorgeSellerBot()
    state = SellerQualificationState(contact_id="c1", location_id="loc1")
    assert state.current_question == 0

    await bot._generate_response(state, "I want to sell my house at 123 Elm St")

    assert len(state.conversation_history) == 1
    assert state.conversation_history[0]["question"] == 0
    assert "123 Elm St" in state.conversation_history[0]["answer"]
    assert state.conversation_history[0]["bot_response"] != ""


# ─── Fix 3: Q4 fallback re-asks Q4 instead of generic punt ───────────────────

def test_seller_fallback_response_q4_re_asks_q4():
    """When Claude fails at Q4, fallback re-asks Q4, not a generic punt."""
    bot = JorgeSellerBot()
    state = SellerQualificationState(contact_id="c1", location_id="loc1")
    state.price_expectation = 300000
    response = bot._get_fallback_response(4, state)
    # Should contain Q4 offer text, not the "Give me a few" punt
    assert "close" in response.lower() or "offer" in response.lower() or "deal" in response.lower()
    assert "Give me a few" not in response


def test_seller_fallback_response_q3_asks_q4():
    """When Claude fails at Q3, fallback asks Q4."""
    bot = JorgeSellerBot()
    state = SellerQualificationState(contact_id="c1", location_id="loc1")
    state.price_expectation = 350000
    response = bot._get_fallback_response(3, state)
    # Q4 text has offer_amount placeholder — should be filled in
    assert "{offer_amount}" not in response
    assert "$" in response


# ─── Fix 5: Urgency affects temperature scoring ───────────────────────────────

def test_seller_urgency_high_tips_borderline_to_warm():
    """High urgency at Q3 tips borderline COLD → WARM."""
    bot = JorgeSellerBot()
    state = SellerQualificationState(contact_id="c1", location_id="loc1")
    state.questions_answered = 3
    state.urgency = "high"
    # Without urgency this would be COLD (only 3/4 answered)
    assert bot._calculate_temperature(state) == "warm"


def test_seller_urgency_low_tips_warm_to_cold():
    """Low urgency tips full-qualified WARM → COLD."""
    bot = JorgeSellerBot()
    state = SellerQualificationState(contact_id="c1", location_id="loc1")
    state.questions_answered = 4
    state.price_expectation = 300000
    state.motivation = "foreclosure"
    state.urgency = "low"
    assert bot._calculate_temperature(state) == "cold"


# ─── Fix 9: Q0 doesn't inflate questions_answered ────────────────────────────

@pytest.mark.asyncio
async def test_seller_q0_does_not_set_questions_answered():
    """After Q0 greeting, questions_answered must remain 0."""
    bot = JorgeSellerBot()
    state = SellerQualificationState(contact_id="c1", location_id="loc1")
    await bot._generate_response(state, "Hi I want to sell")
    assert state.questions_answered == 0


# ─── Fix 10: State deserialization guard ─────────────────────────────────────

@pytest.mark.asyncio
async def test_seller_state_deserialization_ignores_unknown_keys():
    """Extra keys in cached state do not crash deserialization."""

    class DummyCache:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value, ttl=None):
            self.store[key] = value
            return True

    bot = JorgeSellerBot()
    bot.cache = DummyCache()
    state = SellerQualificationState(contact_id="c1", location_id="loc1")
    await bot.save_conversation_state("c1", state)

    # Inject an unknown field
    cached = await bot.cache.get("seller:state:c1")
    cached["unknown_future_field"] = "boom"
    await bot.cache.set("seller:state:c1", cached)

    loaded = await bot.get_conversation_state("c1")
    assert loaded is not None
    assert loaded.contact_id == "c1"


# ─── DB fallback — seller restores state after cache miss ────────────────────

@pytest.mark.asyncio
async def test_seller_db_fallback_restores_state():
    """get_conversation_state falls back to DB when cache is empty."""
    from unittest.mock import MagicMock, patch
    from datetime import datetime, timezone

    class EmptyCache:
        async def get(self, key): return None
        async def set(self, key, value, ttl=None): pass

    bot = JorgeSellerBot()
    bot.cache = EmptyCache()

    mock_row = MagicMock()
    mock_row.current_question = 3
    mock_row.questions_answered = 2
    mock_row.is_qualified = False
    mock_row.stage = "Q3"
    mock_row.extracted_data = {"condition": "needs_major_repairs", "price_expectation": 280000}
    mock_row.conversation_history = []
    mock_row.last_activity = None
    mock_row.conversation_started = datetime.now(timezone.utc)
    mock_row.metadata_json = {"location_id": "loc_test"}

    with patch("bots.seller_bot.jorge_seller_bot.fetch_conversation", return_value=mock_row):
        state = await bot.get_conversation_state("c1")

    assert state is not None
    assert state.current_question == 3
    assert state.condition == "needs_major_repairs"
    assert state.price_expectation == 280000
    assert state.location_id == "loc_test"
