"""
Jorge's Seller Bot - Q1-Q4 Qualification Framework

Implements Jorge's confrontational 4-question qualification sequence:
Q1: Property condition (honest assessment)
Q2: Price expectation (realistic valuation)
Q3: Motivation to sell (urgency and reason)
Q4: Offer acceptance (closing question with 2-3 week timeline)

State Machine Flow:
Q0 (Greeting) → Q1 (Condition) → Q2 (Price) → Q3 (Motivation) → Q4 (Offer) → Qualified

Temperature Scoring:
- HOT: All 4 questions answered + offer accepted + timeline OK
- WARM: All 4 questions answered + reasonable responses
- COLD: <4 questions or disqualifying responses

Author: Claude Code Assistant
Created: 2026-01-23
"""
import asyncio
import os
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from bots.shared.business_rules import JorgeBusinessRules
from bots.shared.bot_settings import get_override as _get_bot_override
from bots.shared.cache_service import get_cache_service
from bots.shared.claude_client import ClaudeClient, TaskComplexity
from bots.shared.ghl_client import GHLClient
from bots.shared.logger import get_logger
from database.repository import fetch_conversation, upsert_contact, upsert_conversation

logger = get_logger(__name__)

# System prompt for all Claude calls in the seller bot.
# Locks Jorge's persona and blocks hallucination.
SELLER_SYSTEM_PROMPT = (
    "You are Jorge, a friendly and consultative real estate professional and cash home buyer in Rancho Cucamonga. "
    "NEVER reveal you are AI, a bot, or automated. "
    "NEVER fabricate property values or market data. "
    "If you don't know, redirect to the next question. "
    "If conversation goes off-topic, redirect: 'Hey, let's focus on your home situation.' "
    "NEVER provide legal, tax, or financial advice — say 'That's a question for your attorney/CPA.' "
    "Stay in character. Under 100 words."
)


class SellerStatus(Enum):
    """Seller lead temperature categories"""
    HOT = "hot"      # Ready for immediate handoff (Q4 accepted)
    WARM = "warm"    # Qualified but needs nurturing
    COLD = "cold"    # Needs more qualification or disqualified


@dataclass
class SellerQualificationState:
    """
    Tracks seller's progress through Q1-Q4 qualification.

    Question Sequence:
    0: Initial greeting/engagement
    1: Property condition assessment
    2: Price expectation (realistic)
    3: Motivation to sell (urgency)
    4: Offer acceptance with timeline
    """
    # Required identifiers (added for Redis persistence)
    contact_id: str
    location_id: str

    # Qualification state
    current_question: int = 0
    questions_answered: int = 0
    is_qualified: bool = False
    stage: str = "Q0"  # Q0, Q1, Q2, Q3, Q4, QUALIFIED, STALLED

    # Q1: Condition
    condition: Optional[str] = None  # "needs_major_repairs", "needs_minor_repairs", "move_in_ready"

    # Q2: Price expectation
    price_expectation: Optional[int] = None  # Dollar amount

    # Q3: Motivation
    motivation: Optional[str] = None  # "job_relocation", "divorce", "foreclosure", etc.
    urgency: Optional[str] = None  # "high", "medium", "low"

    # Q4: Offer acceptance
    offer_accepted: Optional[bool] = None
    timeline_acceptable: Optional[bool] = None  # 2-3 week close

    # Metadata
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    extracted_data: Dict[str, Any] = field(default_factory=dict)  # For dashboard integration
    last_interaction: Optional[datetime] = None
    conversation_started: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def advance_question(self):
        """Move to next question in sequence and update stage"""
        if self.current_question < 4:
            self.current_question += 1
            self.stage = f"Q{self.current_question}"
            logger.info(f"Advanced to Q{self.current_question}")

    def record_answer(self, question_num: int, answer: str, extracted_data: Dict[str, Any]):
        """
        Record answer to a specific question.

        Args:
            question_num: Question number (1-4)
            answer: Raw user response
            extracted_data: Structured data extracted from response
        """
        self.conversation_history.append({
            "question": question_num,
            "answer": answer,
            "bot_response": "",  # filled in by process_seller_message after Claude responds
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "extracted_data": extracted_data
        })
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        # Update questions_answered count
        if question_num > self.questions_answered:
            self.questions_answered = question_num

        # Store extracted data in appropriate fields
        if question_num == 1:
            self.condition = extracted_data.get("condition")
        elif question_num == 2:
            self.price_expectation = extracted_data.get("price_expectation")
        elif question_num == 3:
            self.motivation = extracted_data.get("motivation")
            self.urgency = extracted_data.get("urgency")
        elif question_num == 4:
            self.offer_accepted = extracted_data.get("offer_accepted")
            self.timeline_acceptable = extracted_data.get("timeline_acceptable")

            # Auto-mark as qualified if offer accepted with good timeline
            if self.offer_accepted and self.timeline_acceptable:
                self.is_qualified = True
                self.stage = "QUALIFIED"

        # Update extracted_data field for dashboard
        self.extracted_data.update(extracted_data)

        self.last_interaction = datetime.now(timezone.utc)
        logger.debug(f"Recorded Q{question_num} answer: {extracted_data}")


@dataclass
class SellerResult:
    """Result from seller bot processing"""
    response_message: str
    seller_temperature: str
    questions_answered: int
    qualification_complete: bool
    actions_taken: List[Dict[str, Any]]
    next_steps: str
    analytics: Dict[str, Any]


class JorgeSellerBot:
    """
    Jorge's Seller Bot - Confrontational 4-Question Qualification System.

    Features:
    - Q1-Q4 structured qualification
    - Jorge's authentic confrontational tone
    - State machine conversation flow
    - Automated temperature scoring
    - CMA automation triggers
    - GHL integration for tagging and workflows

    Integration Pattern (from Phase 1):
    - Uses ClaudeClient for AI responses
    - Uses GHLClient for CRM actions
    - Uses JorgeBusinessRules for validation
    - Follows Phase 1 async patterns
    """

    # Jorge's friendly, consultative opening phrases
    JORGE_PHRASES = [
        "Happy to help you out!",
        "Thanks for reaching out — let me ask you a few quick questions.",
        "Let's figure out the best option for your situation.",
        "I appreciate you getting in touch!",
        "Great, let's see what we can do for you.",
        "Happy to take a look at your situation.",
        "Let me get a little more info so I can help you properly.",
        "Glad you reached out — let's get started."
    ]

    # Q1-Q4 Framework (Jorge's exact questions)
    QUALIFICATION_QUESTIONS = {
        1: (
            "What condition is the house in? Does it need major repairs, "
            "minor fixes, or is it move-in ready? Just want to make sure I'm giving you the most accurate picture."
        ),
        2: (
            "What do you think it's worth as-is? I want to know your number, not Zillow's estimate — "
            "what would you realistically expect to get for it in its current condition?"
        ),
        3: (
            "What's motivating the sale? Job relocation, inherited property, looking to downsize — "
            "just want to understand your situation so I can find the right solution for you."
        ),
        4: (
            "Based on what you've shared, I could offer you {offer_amount} cash and close in 2-3 weeks "
            "with no repairs needed on your end. Does that work for your timeline?"
        )
    }

    @property
    def _questions(self) -> dict:
        """Live qualification questions — override-aware, falls back to class constant."""
        raw = _get_bot_override("seller").get("questions")
        if not raw:
            return self.QUALIFICATION_QUESTIONS
        # Override uses string keys ("1"–"4"); normalise to int keys
        if isinstance(next(iter(raw)), str):
            return {int(k): v for k, v in raw.items()}
        return raw

    def __init__(self, ghl_client: Optional[GHLClient] = None):
        """
        Initialize seller bot with Redis persistence.

        Args:
            ghl_client: Optional GHL client instance (creates default if not provided)
        """
        self.claude_client = ClaudeClient()
        self.ghl_client = ghl_client or GHLClient()
        self.cache = get_cache_service()  # Redis cache for persistence
        self.logger = get_logger(__name__)

        # Note: No in-memory _states dict - all state now in Redis
        self.logger.info("Initialized JorgeSellerBot with Redis persistence")

    async def get_conversation_state(
        self,
        contact_id: str
    ) -> Optional[SellerQualificationState]:
        """
        Load conversation state from cache, falling back to DB on cache miss.

        Args:
            contact_id: GHL contact ID

        Returns:
            SellerQualificationState if exists, None otherwise
        """
        key = f"seller:state:{contact_id}"
        state_dict = await self.cache.get(key)

        if not state_dict:
            # Cache miss — try DB fallback (handles MemoryCache restart loss)
            try:
                row = await fetch_conversation(contact_id, "seller")
                if row:
                    ed = row.extracted_data or {}
                    state = SellerQualificationState(
                        contact_id=contact_id,
                        location_id=row.metadata_json.get("location_id", ""),
                        current_question=row.current_question,
                        questions_answered=row.questions_answered,
                        is_qualified=row.is_qualified,
                        stage=row.stage or "Q0",
                        condition=ed.get("condition"),
                        price_expectation=ed.get("price_expectation"),
                        motivation=ed.get("motivation"),
                        urgency=ed.get("urgency"),
                        offer_accepted=ed.get("offer_accepted"),
                        timeline_acceptable=ed.get("timeline_acceptable"),
                        conversation_history=row.conversation_history or [],
                        extracted_data=ed,
                        last_interaction=row.last_activity,
                        conversation_started=row.conversation_started or datetime.now(timezone.utc),
                    )
                    # Re-warm cache so subsequent requests skip DB
                    await self.save_conversation_state(contact_id, state)
                    self.logger.info(f"Restored seller state for {contact_id} from DB")
                    return state
            except Exception as db_err:
                self.logger.warning(f"DB conversation fallback failed for {contact_id}: {db_err}")
            return None

        # Create a copy to avoid modifying the cached object in place
        state_dict = state_dict.copy()

        # Deserialize datetime fields
        if 'last_interaction' in state_dict and state_dict['last_interaction']:
            state_dict['last_interaction'] = datetime.fromisoformat(
                state_dict['last_interaction']
            )
        if 'conversation_started' in state_dict and state_dict['conversation_started']:
            state_dict['conversation_started'] = datetime.fromisoformat(
                state_dict['conversation_started']
            )

        valid_fields = {f.name for f in fields(SellerQualificationState)}
        state_dict = {k: v for k, v in state_dict.items() if k in valid_fields}
        return SellerQualificationState(**state_dict)

    async def save_conversation_state(
        self,
        contact_id: str,
        state: SellerQualificationState,
        temperature: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Save conversation state to Redis with 7-day TTL.

        Args:
            contact_id: GHL contact ID
            state: Current conversation state
        """
        key = f"seller:state:{contact_id}"

        # Convert dataclass to dict and serialize datetime fields
        state_dict = {
            'contact_id': state.contact_id,
            'location_id': state.location_id,
            'current_question': state.current_question,
            'questions_answered': state.questions_answered,
            'is_qualified': state.is_qualified,
            'stage': state.stage,
            'condition': state.condition,
            'price_expectation': state.price_expectation,
            'motivation': state.motivation,
            'urgency': state.urgency,
            'offer_accepted': state.offer_accepted,
            'timeline_acceptable': state.timeline_acceptable,
            'conversation_history': state.conversation_history,
            'extracted_data': state.extracted_data,
            'last_interaction': state.last_interaction.isoformat() if state.last_interaction else None,
            'conversation_started': state.conversation_started.isoformat() if state.conversation_started else None,
        }

        # Save to Redis with 7-day TTL (604,800 seconds)
        await self.cache.set(key, state_dict, ttl=604800)

        # Add to active contacts set (if Redis Set support available)
        if hasattr(self.cache, 'sadd'):
            try:
                await self.cache.sadd("seller:active_contacts", contact_id)
            except Exception as e:
                self.logger.warning(f"Could not add to active contacts set: {e}")

        self.logger.debug(f"Saved state for contact {contact_id}: stage={state.stage}, Q{state.current_question}")

        # Persist to database (best-effort — schema may not be initialized yet)
        try:
            merged_metadata = {"location_id": state.location_id}
            merged_metadata.update(metadata or {})
            await upsert_conversation(
                contact_id=contact_id,
                bot_type="seller",
                stage=state.stage,
                temperature=temperature,
                current_question=state.current_question,
                questions_answered=state.questions_answered,
                is_qualified=state.is_qualified,
                conversation_history=state.conversation_history,
                extracted_data=state.extracted_data,
                last_activity=state.last_interaction,
                conversation_started=state.conversation_started,
                metadata_json=merged_metadata,
            )
        except Exception as db_err:
            self.logger.warning(f"DB upsert_conversation skipped (schema not ready?): {db_err}")

    async def get_all_active_conversations(self) -> List[SellerQualificationState]:
        """
        Get all active seller conversations from Redis.

        Returns:
            List of active conversation states
        """
        states = []

        # Get active contact IDs from Redis Set
        if hasattr(self.cache, 'smembers'):
            try:
                contact_ids = await self.cache.smembers("seller:active_contacts")

                # Decode bytes to strings if needed
                if contact_ids and isinstance(next(iter(contact_ids)), bytes):
                    contact_ids = [cid.decode('utf-8') for cid in contact_ids]
            except Exception as e:
                self.logger.warning(f"Could not get active contacts from set: {e}")
                return []
        else:
            # Fallback: return empty list
            self.logger.warning("Redis Set operations not available, returning empty list")
            return []

        # Load each state
        for contact_id in contact_ids:
            state = await self.get_conversation_state(contact_id)
            if state:
                states.append(state)
            else:
                try:
                    await self.cache.srem("seller:active_contacts", contact_id)
                except Exception as e:
                    self.logger.warning(f"Could not remove stale active contact {contact_id}: {e}")

        return states

    async def delete_conversation_state(self, contact_id: str):
        """
        Delete conversation state from Redis.

        Args:
            contact_id: GHL contact ID
        """
        key = f"seller:state:{contact_id}"
        await self.cache.delete(key)

        # Remove from active contacts set
        if hasattr(self.cache, 'srem'):
            try:
                await self.cache.srem("seller:active_contacts", contact_id)
            except Exception as e:
                self.logger.warning(f"Could not remove from active contacts set: {e}")

        self.logger.info(f"Deleted state for contact {contact_id}")

    async def process_seller_message(
        self,
        contact_id: str,
        location_id: str,
        message: str,
        contact_info: Optional[Dict] = None
    ) -> SellerResult:
        """
        Main entry point for processing seller messages.

        Args:
            contact_id: GHL contact ID
            location_id: GHL location ID
            message: Seller's message text
            contact_info: Optional contact information from GHL

        Returns:
            SellerResult with response and qualification status
        """
        try:
            self.logger.info(f"Processing seller message for contact {contact_id}")

            # Get or create qualification state (now from Redis)
            state = await self._get_or_create_state(contact_id, location_id)

            if contact_info:
                try:
                    await upsert_contact(
                        contact_id=contact_id,
                        location_id=location_id,
                        name=contact_info.get("name") or contact_info.get("full_name"),
                        email=contact_info.get("email"),
                        phone=contact_info.get("phone"),
                    )
                except Exception as db_err:
                    self.logger.warning(f"DB upsert_contact skipped (schema not ready?): {db_err}")

            # Determine current question and generate response
            response_data = await self._generate_response(
                state=state,
                user_message=message,
                contact_info=contact_info
            )

            # Update state based on response (before advancing)
            current_q_for_answer = state.current_question

            # Advance to next question if appropriate (before recording answer)
            if state.current_question < 4 and response_data.get("should_advance", False):
                state.advance_question()

            # Record answer for the question we just asked
            if response_data.get("extracted_data"):
                state.record_answer(
                    question_num=current_q_for_answer,
                    answer=message,
                    extracted_data=response_data["extracted_data"]
                )
                # Store the bot's response so Claude has proper alternating history next turn
                if state.conversation_history:
                    state.conversation_history[-1]["bot_response"] = response_data.get("message", "")

            # Calculate temperature
            temperature = self._calculate_temperature(state)

            # Save state to Redis and DB after updates
            await self.save_conversation_state(
                contact_id,
                state,
                temperature=temperature,
                metadata={
                    "contact_name": contact_info.get("name") if contact_info else None,
                    "property_address": contact_info.get("property_address") if contact_info else None,
                },
            )

            # Determine next steps
            next_steps = self._determine_next_steps(state, temperature)

            # Generate GHL actions
            actions = await self._generate_actions(
                contact_id=contact_id,
                location_id=location_id,
                state=state,
                temperature=temperature
            )

            # Build analytics
            analytics = self._build_analytics(state, temperature)

            # Create result
            result = SellerResult(
                response_message=response_data["message"],
                seller_temperature=temperature,
                questions_answered=state.questions_answered,
                qualification_complete=(state.questions_answered >= 4),
                actions_taken=actions,
                next_steps=next_steps,
                analytics=analytics
            )

            self.logger.info(
                f"Seller {contact_id}: Q{state.current_question}, "
                f"Answered: {state.questions_answered}/4, Temp: {temperature}"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error processing seller message: {e}", exc_info=True)
            try:
                cached = await self.get_conversation_state(contact_id)
                if cached:
                    temperature = self._calculate_temperature(cached)
                    return SellerResult(
                        response_message="I'm interested but need a bit more info. Let me get back to you shortly.",
                        seller_temperature=temperature,
                        questions_answered=cached.questions_answered,
                        qualification_complete=(cached.questions_answered >= 4),
                        actions_taken=[],
                        next_steps="Manual follow-up required",
                        analytics={"error": "Processing error occurred"}
                    )
            except Exception as inner_e:
                self.logger.error(f"Fallback state load also failed: {inner_e}")
            return self._create_fallback_result()

    async def _get_or_create_state(
        self,
        contact_id: str,
        location_id: str
    ) -> SellerQualificationState:
        """Get existing state from Redis or create new one."""
        state = await self.get_conversation_state(contact_id)

        if not state:
            state = SellerQualificationState(
                contact_id=contact_id,
                location_id=location_id,
                current_question=0,
                stage="Q0",
                conversation_started=datetime.now(timezone.utc)
            )
            await self.save_conversation_state(contact_id, state)
            self.logger.info(f"Created new qualification state for {contact_id}")

        return state

    async def _generate_response(
        self,
        state: SellerQualificationState,
        user_message: str,
        contact_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate Jorge's response based on current state.

        Returns:
            Dict with:
                - message: Response text
                - extracted_data: Structured data from user message
                - should_advance: Whether to move to next question
        """
        # Determine which question to ask
        if state.current_question == 0:
            # Initial greeting - move to Q1
            question_text = self._questions[1]
            jorge_intro = self._get_random_jorge_phrase()
            response_message = f"{jorge_intro}. {question_text}"
            # Preserve the initial message in history before advancing
            state.conversation_history.append({
                "question": 0,
                "answer": user_message,
                "bot_response": response_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "extracted_data": {},
            })
            state.advance_question()  # Move to Q1

            return {
                "message": response_message,
                "extracted_data": {},
                "should_advance": False  # Already advanced
            }

        # For Q1-Q4, use Claude to analyze response and ask next question
        current_q = state.current_question

        # Build prompt for Claude
        prompt = self._build_claude_prompt(state, user_message, current_q)

        # Build alternating user/assistant history for Claude (last 10 turns)
        history = []
        for entry in state.conversation_history[-10:]:
            history.append({"role": "user", "content": entry["answer"]})
            bot_reply = entry.get("bot_response", "")
            if bot_reply:
                history.append({"role": "assistant", "content": bot_reply})

        # Get AI response from Claude (system prompt may be overridden via admin settings)
        system_prompt = _get_bot_override("seller").get("system_prompt", SELLER_SYSTEM_PROMPT)
        try:
            llm_response = await self.claude_client.agenerate(
                prompt=prompt,
                system_prompt=system_prompt,
                history=history,
                max_tokens=500
            )
            ai_message = llm_response.content
        except Exception as e:
            self.logger.error(f"Claude API error: {e}")
            ai_message = self._get_fallback_response(current_q, state)

        # Extract data from user's response
        extracted_data = await self._extract_qualification_data(
            user_message=user_message,
            question_num=current_q
        )

        # Determine if we should advance
        should_advance = self._should_advance_question(extracted_data, current_q)

        return {
            "message": ai_message,
            "extracted_data": extracted_data,
            "should_advance": should_advance
        }

    def _build_claude_prompt(
        self,
        state: SellerQualificationState,
        user_message: str,
        current_question: int
    ) -> str:
        """Build prompt for Claude AI to generate Jorge's response"""

        # Get next question text
        next_q = current_question + 1 if current_question < 4 else None
        next_question_text = self._questions.get(next_q, "")

        # Calculate offer amount for Q4 if needed
        if next_q == 4:
            # Jorge's formula: 70-80% of asking price for cash offer
            offer_amount = int((state.price_expectation or 300000) * 0.75)
            next_question_text = next_question_text.format(
                offer_amount=f"${offer_amount:,}"
            )

        prompt = f"""You are Jorge, a friendly and consultative real estate professional and cash home buyer in Rancho Cucamonga.

PERSONALITY TRAITS:
- Warm, professional, and easy to talk to
- Genuinely helpful and focused on finding the best solution for the seller
- Clear and straightforward without being pushy
- Makes sellers feel heard and respected
- Moves efficiently but never makes sellers feel rushed

CURRENT SITUATION:
You just asked: "{self._questions.get(current_question, '')}"

Seller responded: "{user_message}"

TASK:
1. Briefly acknowledge their response (1 sentence max)
2. {"Ask the next question: " + next_question_text if next_q else "Summarize the situation and next steps"}
3. Keep the tone friendly and consultative throughout

RESPONSE (keep under 100 words):"""

        return prompt

    async def _classify_with_claude(
        self,
        user_message: str,
        instruction: str,
        valid_values: List[str],
        default: str
    ) -> str:
        """Use Haiku to classify text when keyword matching fails. Returns default on any error."""
        try:
            prompt = (
                f"{instruction}\n\n"
                f"User message: {user_message}\n\n"
                f"Respond with ONLY one of: {', '.join(valid_values)}"
            )
            response = await self.claude_client.agenerate(
                prompt=prompt,
                system_prompt="Classify the user message. Respond with ONLY the classification label, nothing else.",
                max_tokens=20,
                temperature=0.0,
                complexity=TaskComplexity.ROUTINE,
            )
            result = response.content.strip().lower()
            if result in valid_values:
                return result
            return default
        except Exception:
            return default

    async def _extract_qualification_data(
        self,
        user_message: str,
        question_num: int
    ) -> Dict[str, Any]:
        """
        Extract structured data from user's response.

        Uses pattern matching + AI for robust extraction.
        """
        extracted = {}
        message_lower = user_message.lower()

        if question_num == 1:
            # Q1: Condition
            if any(word in message_lower for word in [
                "major", "significant", "extensive", "needs work", "bad shape",
                "falling apart", "broken", "run down", "rundown", "fixer", "gut",
                "disaster", "terrible", "awful", "wreck", "dump", "outdated",
                "old", "rough", "trashed", "condemned"
            ]):
                extracted["condition"] = "needs_major_repairs"
            elif any(word in message_lower for word in [
                "minor", "small", "few", "cosmetic", "touch up", "paint", "carpet",
                "dated", "okay", "ok", "fine", "alright", "decent", "fair",
                "maintenance", "wear", "showing its age", "aging", "lived in",
                "some work", "little work", "needs some"
            ]):
                extracted["condition"] = "needs_minor_repairs"
            elif any(word in message_lower for word in [
                "ready", "good", "excellent", "perfect", "great shape", "move in",
                "updated", "renovated", "remodeled", "new", "nice", "beautiful",
                "pristine", "great", "well maintained", "well-maintained", "clean"
            ]):
                extracted["condition"] = "move_in_ready"
            else:
                extracted["condition"] = await self._classify_with_claude(
                    user_message,
                    "Classify this home condition description.",
                    ["needs_major_repairs", "needs_minor_repairs", "move_in_ready"],
                    "needs_minor_repairs"
                )

        elif question_num == 2:
            # Q2: Price expectation
            import re
            price_patterns = [
                r'\$?(\d[\d,]*)k',  # $350k or 350k
                r'\$?(\d[\d,]*),000',  # $350,000
                r'\$?(\d[\d,]*)'  # $350000 or 350000 (must start with digit)
            ]

            for pattern in price_patterns:
                match = re.search(pattern, user_message)
                if match:
                    price_str = match.group(1).replace(',', '')
                    if 'k' in user_message.lower():
                        extracted["price_expectation"] = int(price_str) * 1000
                    else:
                        price = int(price_str)
                        # Assume values < 10000 are in thousands (e.g., "350" = $350K)
                        if price < 10000:
                            price *= 1000
                        extracted["price_expectation"] = price
                    break

            if "price_expectation" not in extracted:
                # No digit found — use Haiku to extract price from text like "around three fifty"
                try:
                    haiku_prompt = (
                        "Extract the home price in US dollars as a plain integer (no commas, no $, "
                        "no text). Examples: 'around three fifty' → 350000, 'high threes' → 375000, "
                        f"'between 300 and 400' → 350000. Message: {user_message}"
                    )
                    haiku_resp = await self.claude_client.agenerate(
                        prompt=haiku_prompt,
                        system_prompt="Reply with ONLY the integer price in dollars. Nothing else.",
                        max_tokens=20,
                        temperature=0.0,
                        complexity=TaskComplexity.ROUTINE,
                    )
                    price = int(haiku_resp.content.strip().replace(",", "").replace("$", ""))
                    if price < 10000:
                        price *= 1000
                    extracted["price_expectation"] = price
                except Exception:
                    extracted["price_expectation"] = 300000

        elif question_num == 3:
            # Q3: Motivation
            motivations = {
                "job": "job_relocation",
                "relocation": "job_relocation",
                "relocating": "job_relocation",
                "transfer": "job_relocation",
                "moving": "job_relocation",
                "move": "job_relocation",
                "divorce": "divorce",
                "separation": "divorce",
                "separating": "divorce",
                "foreclosure": "foreclosure",
                "foreclose": "foreclosure",
                "financial": "financial_distress",
                "behind on": "financial_distress",
                "debt": "financial_distress",
                "bankruptcy": "financial_distress",
                "inherited": "inheritance",
                "inheritance": "inheritance",
                "probate": "inheritance",
                "death in": "inheritance",
                "passed away": "inheritance",
                "died": "inheritance",
                "estate": "inheritance",
                "downsize": "downsizing",
                "downsizing": "downsizing",
                "retire": "retirement",
                "retirement": "retirement",
                "retiring": "retirement",
                "upsize": "upsizing",
                "upsizing": "upsizing",
                "medical": "medical_emergency",
                "tenant": "landlord_exit",
                "vacant": "landlord_exit",
                "don't want": "landlord_exit",
                "tired of": "landlord_exit",
            }

            for keyword, motivation_type in motivations.items():
                if keyword in message_lower:
                    extracted["motivation"] = motivation_type
                    break

            if "motivation" not in extracted:
                extracted["motivation"] = await self._classify_with_claude(
                    user_message,
                    "Classify the seller's motivation to sell their home.",
                    ["job_relocation", "divorce", "foreclosure", "financial_distress",
                     "inheritance", "downsizing", "upsizing", "medical_emergency",
                     "retirement", "landlord_exit", "other"],
                    "financial_distress"
                )

            # Detect urgency
            if any(word in message_lower for word in ["asap", "urgent", "immediately", "fast", "quick", "soon"]):
                extracted["urgency"] = "high"
            elif any(word in message_lower for word in ["flexible", "no rush", "whenever", "eventually"]):
                extracted["urgency"] = "low"
            else:
                extracted["urgency"] = "medium"

        elif question_num == 4:
            # Q4: Offer acceptance (independent of timeline)
            if any(word in message_lower for word in [
                "yes", "deal", "accept", "sounds good", "let's do it", "lets do it",
                "sure", "ok", "okay", "works for me", "i'll take it", "ill take it"
            ]):
                extracted["offer_accepted"] = True
            elif any(word in message_lower for word in [
                "no", "can't", "cant", "won't", "wont", "too low", "pass",
                "not interested", "not enough", "need more money"
            ]):
                extracted["offer_accepted"] = False
            else:
                extracted["offer_accepted"] = False

            # Timeline acceptance is independent — check for explicit pushback
            timeline_pushback = any(phrase in message_lower for phrase in [
                "need more time", "too quick", "can't close", "cant close",
                "won't close", "wont close", "not that fast", "need longer",
                "more time", "too fast", "need 30", "need 60", "need 90"
            ])
            if timeline_pushback:
                extracted["timeline_acceptable"] = False
            elif extracted.get("offer_accepted"):
                # Accepting the offer implicitly accepts the 2-3 week close
                extracted["timeline_acceptable"] = True
            else:
                extracted["timeline_acceptable"] = False

        return extracted

    def _should_advance_question(self, extracted_data: Dict[str, Any], current_q: int) -> bool:
        """Determine if we should advance to next question based on extracted data"""

        if current_q == 1:
            return "condition" in extracted_data
        elif current_q == 2:
            return "price_expectation" in extracted_data
        elif current_q == 3:
            return "motivation" in extracted_data
        elif current_q == 4:
            return "offer_accepted" in extracted_data

        return False

    def _calculate_temperature(self, state: SellerQualificationState) -> str:
        """
        Calculate seller temperature based on qualification state.

        HOT: All 4 questions + offer accepted + timeline OK
        WARM: All 4 questions + reasonable responses but no offer acceptance
        COLD: <4 questions or disqualifying responses

        Urgency modifies borderline WARM/COLD decisions:
        - high urgency: tip borderline COLD → WARM
        - low urgency: tip borderline WARM → COLD
        """
        # HOT criteria
        if (state.questions_answered >= 4 and
            state.offer_accepted and
            state.timeline_acceptable):
            return SellerStatus.HOT.value

        # WARM criteria
        if state.questions_answered >= 4:
            # Check if within Jorge's business rules
            if state.price_expectation:
                in_range = (JorgeBusinessRules.MIN_BUDGET <=
                           state.price_expectation <=
                           JorgeBusinessRules.MAX_BUDGET)
                if in_range and state.motivation:
                    # Low urgency tips WARM → COLD
                    if state.urgency == "low":
                        return SellerStatus.COLD.value
                    return SellerStatus.WARM.value

        # High urgency tips borderline COLD → WARM when close to qualification
        if state.urgency == "high" and state.questions_answered >= 3:
            return SellerStatus.WARM.value

        # COLD otherwise
        return SellerStatus.COLD.value

    def _determine_next_steps(self, state: SellerQualificationState, temperature: str) -> str:
        """Determine next steps based on qualification state"""

        if temperature == SellerStatus.HOT.value:
            return "Schedule immediate consultation call - HOT lead ready to close"
        elif temperature == SellerStatus.WARM.value:
            return "Continue nurturing with follow-up sequence - qualified but needs time"
        elif state.current_question < 4:
            remaining = 4 - state.current_question
            return f"Continue qualification - {remaining} questions remaining"
        else:
            return "Review qualification data and determine if lead is viable"

    async def _generate_actions(
        self,
        contact_id: str,
        location_id: str,
        state: SellerQualificationState,
        temperature: str
    ) -> List[Dict[str, Any]]:
        """
        Generate GHL actions based on qualification state.

        Actions:
        - Add temperature tags (seller_hot, seller_warm, seller_cold)
        - Update custom fields (seller_temperature, questions_answered, etc.)
        - Trigger workflows (CMA automation for HOT leads)
        """
        actions = []

        # Remove stale temperature tags before adding the current one
        for other_temp in ["hot", "warm", "cold"]:
            if other_temp != temperature:
                actions.append({"type": "remove_tag", "tag": f"seller_{other_temp}"})

        # Add temperature tag
        actions.append({
            "type": "add_tag",
            "tag": f"seller_{temperature}"
        })

        # Update custom fields
        actions.append({
            "type": "update_custom_field",
            "field": "seller_temperature",
            "value": temperature
        })

        actions.append({
            "type": "update_custom_field",
            "field": "seller_questions_answered",
            "value": str(state.questions_answered)
        })

        if state.condition:
            actions.append({
                "type": "update_custom_field",
                "field": "property_condition",
                "value": state.condition
            })

        if state.price_expectation:
            actions.append({
                "type": "update_custom_field",
                "field": "seller_price_expectation",
                "value": str(state.price_expectation)
            })

        if state.motivation:
            actions.append({
                "type": "update_custom_field",
                "field": "seller_motivation",
                "value": state.motivation
            })

        # Trigger CMA automation for HOT leads
        if temperature == SellerStatus.HOT.value:
            actions.append({
                "type": "trigger_workflow",
                "workflow_id": os.environ.get("HOT_SELLER_WORKFLOW_ID", "577d56c4-28af-4668-8d84-80f5db234f48"),
                "workflow_name": "CMA Report Generation"
            })

        # Apply actions to GHL — hard 10s deadline so Render never times out
        try:
            await asyncio.wait_for(
                self._apply_ghl_actions(contact_id, location_id, actions),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            self.logger.warning(
                f"GHL actions timed out for {contact_id} — tags/workflows will sync on next message"
            )
        except Exception as e:
            self.logger.error(f"Failed to apply GHL actions: {e}")

        return actions

    async def _apply_ghl_actions(
        self,
        contact_id: str,
        location_id: str,
        actions: List[Dict[str, Any]]
    ) -> None:
        """Apply actions to GHL contact"""

        for action in actions:
            try:
                action_type = action.get("type")

                if action_type == "add_tag":
                    await self.ghl_client.add_tag(contact_id, action["tag"])

                elif action_type == "remove_tag":
                    await self.ghl_client.remove_tag(contact_id, action["tag"])

                elif action_type == "update_custom_field":
                    await self.ghl_client.update_custom_field(
                        contact_id, action["field"], action["value"]
                    )

                elif action_type == "trigger_workflow":
                    self.logger.info(
                        f"Triggering workflow: {action.get('workflow_name', 'Unknown')} "
                        f"for contact {contact_id}"
                    )
                    await self.ghl_client.trigger_workflow(contact_id, action["workflow_id"])

            except Exception as e:
                self.logger.error(f"Failed to apply action {action_type}: {e}")

    def _build_analytics(
        self,
        state: SellerQualificationState,
        temperature: str
    ) -> Dict[str, Any]:
        """Build analytics dictionary for seller"""

        return {
            "seller_temperature": temperature,
            "questions_answered": state.questions_answered,
            "qualification_progress": f"{state.questions_answered}/4",
            "qualification_complete": state.questions_answered >= 4,
            "property_condition": state.condition,
            "price_expectation": state.price_expectation,
            "motivation": state.motivation,
            "urgency": state.urgency,
            "offer_accepted": state.offer_accepted,
            "timeline_acceptable": state.timeline_acceptable,
            "last_interaction": state.last_interaction.isoformat() if state.last_interaction else None
        }

    async def get_seller_analytics(
        self,
        contact_id: str,
        location_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a seller lead.

        Args:
            contact_id: GHL contact ID
            location_id: GHL location ID

        Returns:
            Analytics dictionary with qualification status and metrics
        """
        state = await self._get_or_create_state(contact_id, location_id)
        temperature = self._calculate_temperature(state)
        return self._build_analytics(state, temperature)

    def _get_random_jorge_phrase(self) -> str:
        """Get a random Jorge opening phrase (override-aware)."""
        import random
        phrases = _get_bot_override("seller").get("jorge_phrases", self.JORGE_PHRASES)
        return random.choice(phrases)

    def _get_fallback_response(self, question_num: int, state: Optional["SellerQualificationState"] = None) -> str:
        """Get fallback response if AI fails. Re-asks current question when there is no next question."""
        jorge_phrase = self._get_random_jorge_phrase()
        # Use next question if available, otherwise re-ask the current question
        question = self._questions.get(question_num + 1) or self._questions.get(question_num, "")

        if question:
            if "{offer_amount}" in question:
                offer_amount = int(((state.price_expectation if state else None) or 300000) * 0.75)
                question = question.format(offer_amount=f"${offer_amount:,}")
            return f"{jorge_phrase}. {question}"
        else:
            return "Look, something came up. Give me a few and I'll text you back."

    def _create_fallback_result(self) -> SellerResult:
        """Create safe fallback result on error"""
        return SellerResult(
            response_message="I'm interested but need a bit more info. Let me get back to you shortly.",
            seller_temperature="cold",
            questions_answered=0,
            qualification_complete=False,
            actions_taken=[],
            next_steps="Manual follow-up required",
            analytics={"error": "Processing error occurred"}
        )


# Factory function
def create_seller_bot(ghl_client: Optional[GHLClient] = None) -> JorgeSellerBot:
    """Create and configure Jorge's seller bot"""
    return JorgeSellerBot(ghl_client=ghl_client)

# Alias for tests
SellerBotService = JorgeSellerBot
