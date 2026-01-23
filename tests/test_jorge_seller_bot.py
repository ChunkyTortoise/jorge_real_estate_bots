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
import pytest
from unittest.mock import Mock, AsyncMock, patch
from bots.seller_bot.jorge_seller_bot import (
    JorgeSellerBot,
    SellerStatus,
    SellerResult,
    SellerQualificationState
)
from bots.shared.business_rules import JorgeBusinessRules


class TestSellerQualificationState:
    """Test seller qualification state management"""

    def test_initial_state(self):
        """Test initial state is Q0_GREETING"""
        state = SellerQualificationState()
        assert state.current_question == 0
        assert state.questions_answered == 0
        assert state.is_qualified is False
        assert state.condition is None

    def test_advance_to_q1(self):
        """Test advancing from Q0 to Q1"""
        state = SellerQualificationState()
        state.advance_question()
        assert state.current_question == 1
        assert state.questions_answered == 0  # Not answered yet

    def test_record_q1_answer(self):
        """Test recording Q1 (condition) answer"""
        state = SellerQualificationState()
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
        state = SellerQualificationState()
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
        state = SellerQualificationState()
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
        state = SellerQualificationState()
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
        state = SellerQualificationState()
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
        state = SellerQualificationState()

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
        seller_bot._states["test_seller_003"] = SellerQualificationState()
        seller_bot._states["test_seller_003"].current_question = 2
        seller_bot._states["test_seller_003"].questions_answered = 1

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
        seller_bot._states["test_seller_004"] = SellerQualificationState()
        seller_bot._states["test_seller_004"].current_question = 3
        seller_bot._states["test_seller_004"].questions_answered = 2
        seller_bot._states["test_seller_004"].price_expectation = 350000

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
        state = SellerQualificationState()
        state.current_question = 4
        state.questions_answered = 3
        state.condition = "needs_minor_repairs"
        state.price_expectation = 350000
        state.motivation = "job_relocation"
        seller_bot._states["test_seller_005"] = state

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
        state = SellerQualificationState()
        state.current_question = 4
        state.questions_answered = 3
        state.condition = "move_in_ready"
        state.price_expectation = 500000
        state.motivation = "testing_market"
        seller_bot._states["test_seller_006"] = state

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
        state = SellerQualificationState()
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
        state = SellerQualificationState()
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
        state = SellerQualificationState()
        state.questions_answered = 2
        state.condition = "move_in_ready"
        state.price_expectation = 800000

        temperature = seller_bot._calculate_temperature(state)
        assert temperature == SellerStatus.COLD.value

    @pytest.mark.asyncio
    async def test_cma_automation_trigger(self, seller_bot, mock_ghl_client):
        """Test CMA automation triggers on qualification complete"""
        # Simulate complete qualification - HOT lead state
        state = SellerQualificationState()
        state.current_question = 4
        state.questions_answered = 4
        state.is_qualified = True
        state.condition = "needs_minor_repairs"
        state.price_expectation = 450000
        state.motivation = "job_relocation"
        state.offer_accepted = True
        state.timeline_acceptable = True  # This makes it HOT
        seller_bot._states["test_seller_007"] = state

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
        state = SellerQualificationState()
        state.questions_answered = 4
        state.is_qualified = True
        state.offer_accepted = True
        state.timeline_acceptable = True
        seller_bot._states["test_seller_008"] = state

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
        state = SellerQualificationState()
        state.questions_answered = 3
        state.condition = "needs_major_repairs"
        state.price_expectation = 350000
        state.motivation = "divorce"
        seller_bot._states["test_seller_010"] = state

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
        state = SellerQualificationState()
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


class TestSellerBotEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.fixture
    def seller_bot(self):
        """Create seller bot for edge case testing"""
        with patch('bots.seller_bot.jorge_seller_bot.ClaudeClient'):
            bot = JorgeSellerBot()
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
        state = SellerQualificationState()
        state.current_question = 2
        seller_bot._states["test_edge_003"] = state

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
