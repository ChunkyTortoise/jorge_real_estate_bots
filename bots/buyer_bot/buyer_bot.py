"""
Jorge's Buyer Bot - Qualification + Property Matching

Qualification Flow:
Q0 Greeting -> Q1 Preferences -> Q2 Pre-approval -> Q3 Timeline -> Q4 Motivation -> Qualified
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from bots.shared.logger import get_logger
from bots.shared.claude_client import ClaudeClient
from bots.shared.ghl_client import GHLClient
from bots.shared.cache_service import get_cache_service
from bots.shared.config import settings
from bots.shared.business_rules import JorgeBusinessRules
from bots.buyer_bot.buyer_prompts import BUYER_QUESTIONS, JORGE_BUYER_PHRASES, build_buyer_prompt
from database.repository import (
    upsert_contact,
    upsert_conversation,
    upsert_buyer_preferences,
    fetch_properties,
)

logger = get_logger(__name__)


class BuyerStatus:
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


@dataclass
class BuyerQualificationState:
    contact_id: str
    location_id: str

    current_question: int = 0
    questions_answered: int = 0
    is_qualified: bool = False
    stage: str = "Q0"

    beds_min: Optional[int] = None
    baths_min: Optional[float] = None
    sqft_min: Optional[int] = None
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    preferred_location: Optional[str] = None

    preapproved: Optional[bool] = None
    timeline_days: Optional[int] = None
    motivation: Optional[str] = None

    matches: List[Dict[str, Any]] = field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    last_interaction: Optional[datetime] = None
    conversation_started: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def advance_question(self):
        if self.current_question < 4:
            self.current_question += 1
            self.stage = f"Q{self.current_question}"

    def record_answer(self, question_num: int, answer: str, extracted_data: Dict[str, Any]):
        self.conversation_history.append({
            "question": question_num,
            "answer": answer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "extracted_data": extracted_data,
        })
        if question_num > self.questions_answered:
            self.questions_answered = question_num

        if question_num == 1:
            self.beds_min = extracted_data.get("beds_min")
            self.baths_min = extracted_data.get("baths_min")
            self.sqft_min = extracted_data.get("sqft_min")
            self.price_min = extracted_data.get("price_min")
            self.price_max = extracted_data.get("price_max")
            self.preferred_location = extracted_data.get("preferred_location")
        elif question_num == 2:
            self.preapproved = extracted_data.get("preapproved")
        elif question_num == 3:
            self.timeline_days = extracted_data.get("timeline_days")
        elif question_num == 4:
            self.motivation = extracted_data.get("motivation")
            if self.preapproved and self.timeline_days and self.timeline_days <= 30:
                self.is_qualified = True
                self.stage = "QUALIFIED"

        self.extracted_data.update(extracted_data)
        self.last_interaction = datetime.now(timezone.utc)


@dataclass
class BuyerResult:
    response_message: str
    buyer_temperature: str
    questions_answered: int
    qualification_complete: bool
    actions_taken: List[Dict[str, Any]]
    next_steps: str
    analytics: Dict[str, Any]
    matches: List[Dict[str, Any]]


class JorgeBuyerBot:
    """Buyer bot for preference extraction and property matching."""

    def __init__(self, ghl_client: Optional[GHLClient] = None):
        self.claude_client = ClaudeClient()
        self.ghl_client = ghl_client or GHLClient()
        self.cache = get_cache_service()
        self.logger = get_logger(__name__)

    async def process_buyer_message(
        self,
        contact_id: str,
        location_id: str,
        message: str,
        contact_info: Optional[Dict[str, Any]] = None,
    ) -> BuyerResult:
        state = await self._get_or_create_state(contact_id, location_id)

        if contact_info:
            await upsert_contact(
                contact_id=contact_id,
                location_id=location_id,
                name=contact_info.get("name") or contact_info.get("full_name"),
                email=contact_info.get("email"),
                phone=contact_info.get("phone"),
            )

        response = await self._generate_response(state, message)

        extracted_data = response.get("extracted_data", {})
        should_advance = response.get("should_advance", False)

        if state.current_question > 0:
            state.record_answer(state.current_question, message, extracted_data)

        if should_advance:
            state.advance_question()

        # Update matches after Q1 or later
        if state.questions_answered >= 1:
            state.matches = await self._match_properties(state)

        temperature = self._calculate_temperature(state)
        actions = await self._generate_actions(contact_id, location_id, state, temperature)
        await self.save_conversation_state(contact_id, state, temperature)

        return BuyerResult(
            response_message=response["message"],
            buyer_temperature=temperature,
            questions_answered=state.questions_answered,
            qualification_complete=state.questions_answered >= 4,
            actions_taken=actions,
            next_steps=self._determine_next_steps(state, temperature),
            analytics=self._build_analytics(state, temperature),
            matches=state.matches,
        )

    async def _get_or_create_state(self, contact_id: str, location_id: str) -> BuyerQualificationState:
        key = f"buyer:state:{contact_id}"
        state_dict = await self.cache.get(key)
        if state_dict:
            state_dict = state_dict.copy()
            if state_dict.get("last_interaction"):
                state_dict["last_interaction"] = datetime.fromisoformat(state_dict["last_interaction"])
            if state_dict.get("conversation_started"):
                state_dict["conversation_started"] = datetime.fromisoformat(state_dict["conversation_started"])
            return BuyerQualificationState(**state_dict)

        state = BuyerQualificationState(contact_id=contact_id, location_id=location_id)
        await self.save_conversation_state(contact_id, state)
        return state

    async def save_conversation_state(
        self,
        contact_id: str,
        state: BuyerQualificationState,
        temperature: Optional[str] = None,
    ) -> None:
        key = f"buyer:state:{contact_id}"
        state_dict = {
            "contact_id": state.contact_id,
            "location_id": state.location_id,
            "current_question": state.current_question,
            "questions_answered": state.questions_answered,
            "is_qualified": state.is_qualified,
            "stage": state.stage,
            "beds_min": state.beds_min,
            "baths_min": state.baths_min,
            "sqft_min": state.sqft_min,
            "price_min": state.price_min,
            "price_max": state.price_max,
            "preferred_location": state.preferred_location,
            "preapproved": state.preapproved,
            "timeline_days": state.timeline_days,
            "motivation": state.motivation,
            "matches": state.matches,
            "conversation_history": state.conversation_history,
            "extracted_data": state.extracted_data,
            "last_interaction": state.last_interaction.isoformat() if state.last_interaction else None,
            "conversation_started": state.conversation_started.isoformat() if state.conversation_started else None,
        }
        await self.cache.set(key, state_dict, ttl=604800)

        # Persist to database
        await upsert_conversation(
            contact_id=contact_id,
            bot_type="buyer",
            stage=state.stage,
            temperature=temperature,
            current_question=state.current_question,
            questions_answered=state.questions_answered,
            is_qualified=state.is_qualified,
            conversation_history=state.conversation_history,
            extracted_data=state.extracted_data,
            last_activity=state.last_interaction,
            conversation_started=state.conversation_started,
            metadata_json={
                "preferred_location": state.preferred_location,
            },
        )

        await upsert_buyer_preferences(
            contact_id=contact_id,
            location_id=state.location_id,
            beds_min=state.beds_min,
            baths_min=state.baths_min,
            sqft_min=state.sqft_min,
            price_min=state.price_min,
            price_max=state.price_max,
            preapproved=state.preapproved,
            timeline_days=state.timeline_days,
            motivation=state.motivation,
            temperature=temperature,
            preferences_json={
                "beds_min": state.beds_min,
                "baths_min": state.baths_min,
                "sqft_min": state.sqft_min,
                "price_min": state.price_min,
                "price_max": state.price_max,
                "preferred_location": state.preferred_location,
            },
            matches_json=state.matches,
        )

    async def _generate_response(self, state: BuyerQualificationState, user_message: str) -> Dict[str, Any]:
        if state.current_question == 0:
            jorge_intro = self._get_random_jorge_phrase()
            question_text = BUYER_QUESTIONS[1]
            response_message = f"{jorge_intro}. {question_text}"
            state.advance_question()
            return {"message": response_message, "extracted_data": {}, "should_advance": False}

        current_q = state.current_question
        next_q = current_q + 1 if current_q < 4 else None
        next_question_text = BUYER_QUESTIONS.get(next_q, "Let's lock in the details.")
        prompt = build_buyer_prompt(current_q, user_message, next_question_text)

        try:
            llm_response = await self.claude_client.agenerate(prompt=prompt, max_tokens=400)
            ai_message = llm_response.content
        except Exception as e:
            self.logger.error(f"Claude API error: {e}")
            ai_message = next_question_text

        extracted_data = await self._extract_qualification_data(user_message, current_q)
        should_advance = self._should_advance_question(extracted_data, current_q)

        return {"message": ai_message, "extracted_data": extracted_data, "should_advance": should_advance}

    async def _extract_qualification_data(self, user_message: str, question_num: int) -> Dict[str, Any]:
        msg = user_message.lower()
        extracted: Dict[str, Any] = {}

        if question_num == 1:
            import re
            bed_match = re.search(r"(\d+)\s*(bed|beds|br)", msg)
            bath_match = re.search(r"(\d+(?:\.\d+)?)\s*(bath|baths|ba)", msg)
            sqft_match = re.search(r"(\d{3,5})\s*(sqft|square feet|sq ft)", msg)
            price_match = re.findall(r"\$?([\d,]+)k?", msg)

            if bed_match:
                extracted["beds_min"] = int(bed_match.group(1))
            if bath_match:
                extracted["baths_min"] = float(bath_match.group(1))
            if sqft_match:
                extracted["sqft_min"] = int(sqft_match.group(1))

            if price_match:
                parsed = []
                for val in price_match:
                    num = int(val.replace(",", ""))
                    if "k" in msg and num < 10000:
                        num *= 1000
                    parsed.append(num)
                if len(parsed) >= 2:
                    extracted["price_min"] = min(parsed)
                    extracted["price_max"] = max(parsed)
                elif len(parsed) == 1:
                    extracted["price_max"] = parsed[0]

            # location (simple heuristic)
            for area in JorgeBusinessRules.SERVICE_AREAS:
                if area.lower() in msg:
                    extracted["preferred_location"] = area
                    break

        elif question_num == 2:
            if any(word in msg for word in ["preapproved", "pre-approved", "pre approved", "approved", "cash"]):
                extracted["preapproved"] = True
            elif any(word in msg for word in ["not", "no", "working on it"]):
                extracted["preapproved"] = False

        elif question_num == 3:
            if any(word in msg for word in ["asap", "immediately", "now", "urgent"]):
                extracted["timeline_days"] = 30
            elif "month" in msg:
                import re
                match = re.search(r"(\d+)\s*month", msg)
                if match:
                    extracted["timeline_days"] = int(match.group(1)) * 30
            elif "week" in msg:
                import re
                match = re.search(r"(\d+)\s*week", msg)
                if match:
                    extracted["timeline_days"] = int(match.group(1)) * 7

        elif question_num == 4:
            motivations = {
                "job": "job_relocation",
                "family": "growing_family",
                "investment": "investment",
                "school": "school_district",
                "downsizing": "downsizing",
                "upsizing": "upsizing",
            }
            for keyword, value in motivations.items():
                if keyword in msg:
                    extracted["motivation"] = value
                    break

        return extracted

    def _should_advance_question(self, extracted_data: Dict[str, Any], current_q: int) -> bool:
        if current_q == 1:
            return any(k in extracted_data for k in ["beds_min", "price_max", "preferred_location"])
        if current_q == 2:
            return "preapproved" in extracted_data
        if current_q == 3:
            return "timeline_days" in extracted_data
        if current_q == 4:
            return "motivation" in extracted_data
        return False

    def _calculate_temperature(self, state: BuyerQualificationState) -> str:
        if state.preapproved and state.timeline_days and state.timeline_days <= 30:
            return BuyerStatus.HOT
        if state.timeline_days and state.timeline_days <= 90:
            return BuyerStatus.WARM
        return BuyerStatus.COLD

    async def _match_properties(self, state: BuyerQualificationState) -> List[Dict[str, Any]]:
        properties = await fetch_properties(
            city=state.preferred_location,
            price_min=state.price_min,
            price_max=state.price_max,
            beds_min=state.beds_min,
            baths_min=state.baths_min,
            sqft_min=state.sqft_min,
            limit=100,
        )

        scored = []
        for prop in properties:
            score = self._score_property(state, prop)
            scored.append({
                "property_id": prop.id,
                "address": prop.address,
                "city": prop.city,
                "price": prop.price,
                "beds": prop.beds,
                "baths": prop.baths,
                "sqft": prop.sqft,
                "score": score,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:10]

    def _score_property(self, state: BuyerQualificationState, prop) -> float:
        score = 0.0
        if state.beds_min and prop.beds:
            score += 2.0 if prop.beds >= state.beds_min else 0.0
        if state.baths_min and prop.baths:
            score += 2.0 if prop.baths >= state.baths_min else 0.0
        if state.sqft_min and prop.sqft:
            score += 2.0 if prop.sqft >= state.sqft_min else 0.0
        if state.price_max and prop.price:
            score += 2.0 if prop.price <= state.price_max else 0.0
        if state.preferred_location and prop.city:
            score += 2.0 if state.preferred_location.lower() in prop.city.lower() else 0.0
        return score

    async def _generate_actions(
        self,
        contact_id: str,
        location_id: str,
        state: BuyerQualificationState,
        temperature: str,
    ) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []

        actions.append({"type": "add_tag", "tag": f"buyer_{temperature}"})
        actions.append({"type": "update_custom_field", "field": "buyer_temperature", "value": temperature})
        if state.beds_min:
            actions.append({"type": "update_custom_field", "field": "buyer_beds_min", "value": str(state.beds_min)})
        if state.baths_min:
            actions.append({"type": "update_custom_field", "field": "buyer_baths_min", "value": str(state.baths_min)})
        if state.sqft_min:
            actions.append({"type": "update_custom_field", "field": "buyer_sqft_min", "value": str(state.sqft_min)})
        if state.price_min:
            actions.append({"type": "update_custom_field", "field": "buyer_price_min", "value": str(state.price_min)})
        if state.price_max:
            actions.append({"type": "update_custom_field", "field": "buyer_price_max", "value": str(state.price_max)})
        if state.preferred_location:
            actions.append({"type": "update_custom_field", "field": "buyer_location", "value": state.preferred_location})

        if temperature == BuyerStatus.HOT and settings.buyer_alert_workflow_id:
            actions.append({
                "type": "trigger_workflow",
                "workflow_id": settings.buyer_alert_workflow_id,
                "workflow_name": "Buyer Property Alert",
            })

        if settings.buyer_pipeline_id:
            actions.append({
                "type": "upsert_opportunity",
                "pipeline_id": settings.buyer_pipeline_id,
                "status": "qualified",
            })

        await self._apply_ghl_actions(contact_id, actions)
        return actions

    async def _apply_ghl_actions(self, contact_id: str, actions: List[Dict[str, Any]]) -> None:
        for action in actions:
            action_type = action.get("type")
            try:
                if action_type == "add_tag":
                    await self.ghl_client.add_tag(contact_id, action["tag"])
                elif action_type == "update_custom_field":
                    await self.ghl_client.update_custom_field(contact_id, action["field"], action["value"])
                elif action_type == "trigger_workflow":
                    # TODO: implement in GHL client when API available
                    logger.info(f"Trigger workflow {action.get('workflow_id')} for {contact_id}")
                elif action_type == "upsert_opportunity":
                    # Minimal: create new opportunity
                    await self.ghl_client.create_opportunity({
                        "name": f"Buyer {contact_id}",
                        "contactId": contact_id,
                        "pipelineId": action.get("pipeline_id"),
                        "status": action.get("status", "open"),
                    })
            except Exception as e:
                logger.error(f"Failed to apply action {action_type}: {e}")

    def _build_analytics(self, state: BuyerQualificationState, temperature: str) -> Dict[str, Any]:
        return {
            "buyer_temperature": temperature,
            "questions_answered": state.questions_answered,
            "qualification_complete": state.questions_answered >= 4,
            "preapproved": state.preapproved,
            "timeline_days": state.timeline_days,
            "motivation": state.motivation,
            "preferences": {
                "beds_min": state.beds_min,
                "baths_min": state.baths_min,
                "sqft_min": state.sqft_min,
                "price_min": state.price_min,
                "price_max": state.price_max,
                "preferred_location": state.preferred_location,
            },
        }

    def _determine_next_steps(self, state: BuyerQualificationState, temperature: str) -> str:
        if temperature == BuyerStatus.HOT:
            return "Schedule showings immediately and send curated matches"
        if temperature == BuyerStatus.WARM:
            return "Send weekly property alerts and nurture"
        return "Continue qualification and capture missing preferences"

    def _get_random_jorge_phrase(self) -> str:
        import random
        return random.choice(JORGE_BUYER_PHRASES)

    async def get_buyer_analytics(self, contact_id: str, location_id: str) -> Dict[str, Any]:
        state = await self._get_or_create_state(contact_id, location_id)
        temperature = self._calculate_temperature(state)
        return self._build_analytics(state, temperature)

    async def get_preferences(self, contact_id: str, location_id: str) -> Dict[str, Any]:
        state = await self._get_or_create_state(contact_id, location_id)
        return {
            "beds_min": state.beds_min,
            "baths_min": state.baths_min,
            "sqft_min": state.sqft_min,
            "price_min": state.price_min,
            "price_max": state.price_max,
            "preferred_location": state.preferred_location,
            "preapproved": state.preapproved,
            "timeline_days": state.timeline_days,
            "motivation": state.motivation,
        }

    async def get_matches(self, contact_id: str, location_id: str) -> List[Dict[str, Any]]:
        state = await self._get_or_create_state(contact_id, location_id)
        if not state.matches:
            state.matches = await self._match_properties(state)
            await self.save_conversation_state(contact_id, state, self._calculate_temperature(state))
        return state.matches

    async def get_all_active_conversations(self) -> List[BuyerQualificationState]:
        # Redis set is not implemented in CacheService; return empty for now
        return []


def create_buyer_bot(ghl_client: Optional[GHLClient] = None) -> JorgeBuyerBot:
    return JorgeBuyerBot(ghl_client=ghl_client)
