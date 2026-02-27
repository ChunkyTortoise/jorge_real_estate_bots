"""
Jorge's Buyer Bot - Qualification + Property Matching

Qualification Flow:
Q0 Greeting -> Q1 Preferences -> Q2 Pre-approval -> Q3 Timeline -> Q4 Motivation -> Qualified
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bots.buyer_bot.buyer_prompts import BUYER_QUESTIONS, BUYER_SYSTEM_PROMPT, JORGE_BUYER_PHRASES, build_buyer_prompt
from bots.shared.business_rules import JorgeBusinessRules
from bots.shared.cache_service import get_cache_service
from bots.shared.claude_client import ClaudeClient
from bots.shared.config import settings
from bots.shared.ghl_client import GHLClient
from bots.shared.logger import get_logger
from database.repository import (
    fetch_conversation,
    fetch_properties,
    upsert_buyer_preferences,
    upsert_contact,
    upsert_conversation,
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
    opportunity_created: bool = False

    def advance_question(self):
        if self.current_question < 4:
            self.current_question += 1
            self.stage = f"Q{self.current_question}"

    def record_answer(self, question_num: int, answer: str, extracted_data: Dict[str, Any]):
        self.conversation_history.append({
            "question": question_num,
            "answer": answer,
            "bot_response": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "extracted_data": extracted_data,
        })
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
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

        original_q = state.current_question
        response = await self._generate_response(state, message)

        extracted_data = response.get("extracted_data", {})
        should_advance = response.get("should_advance", False)

        if original_q > 0:
            state.record_answer(state.current_question, message, extracted_data)
            # Store bot response so Claude has proper alternating history next turn
            if state.conversation_history:
                state.conversation_history[-1]["bot_response"] = response.get("message", "")

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
            valid_fields = {f.name for f in fields(BuyerQualificationState)}
            state_dict = {k: v for k, v in state_dict.items() if k in valid_fields}
            return BuyerQualificationState(**state_dict)

        # Cache miss — try DB fallback (handles MemoryCache restart loss)
        try:
            row = await fetch_conversation(contact_id, "buyer")
            if row:
                ed = row.extracted_data or {}
                state = BuyerQualificationState(
                    contact_id=contact_id,
                    location_id=row.metadata_json.get("location_id", location_id),
                    current_question=row.current_question,
                    questions_answered=row.questions_answered,
                    is_qualified=row.is_qualified,
                    stage=row.stage or "Q0",
                    beds_min=ed.get("beds_min"),
                    baths_min=ed.get("baths_min"),
                    sqft_min=ed.get("sqft_min"),
                    price_min=ed.get("price_min"),
                    price_max=ed.get("price_max"),
                    preferred_location=ed.get("preferred_location"),
                    preapproved=ed.get("preapproved"),
                    timeline_days=ed.get("timeline_days"),
                    motivation=ed.get("motivation"),
                    conversation_history=row.conversation_history or [],
                    extracted_data=ed,
                    last_interaction=row.last_activity,
                    conversation_started=row.conversation_started or datetime.now(timezone.utc),
                )
                # Re-warm cache so subsequent requests skip DB
                await self.save_conversation_state(contact_id, state)
                self.logger.info(f"Restored buyer state for {contact_id} from DB")
                return state
        except Exception as db_err:
            self.logger.warning(f"DB conversation fallback failed for {contact_id}: {db_err}")

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
            "opportunity_created": state.opportunity_created,
        }
        await self.cache.set(key, state_dict, ttl=604800)
        if hasattr(self.cache, "sadd"):
            try:
                await self.cache.sadd("buyer:active_contacts", contact_id, ttl=604800)
            except Exception as e:
                self.logger.warning(f"Could not add to active contacts set: {e}")

        # Persist to database (best-effort — schema may not be initialized yet)
        try:
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
                    "location_id": state.location_id,
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
        except Exception as db_err:
            self.logger.warning(f"DB persist skipped (schema not ready?): {db_err}")

    async def _generate_response(self, state: BuyerQualificationState, user_message: str) -> Dict[str, Any]:
        if state.current_question == 0:
            jorge_intro = self._get_random_jorge_phrase()
            question_text = BUYER_QUESTIONS[1]
            response_message = f"{jorge_intro}. {question_text}"
            # Preserve the initial message in history before advancing
            state.conversation_history.append({
                "question": 0,
                "answer": user_message,
                "bot_response": response_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "extracted_data": {},
            })
            state.advance_question()
            return {"message": response_message, "extracted_data": {}, "should_advance": False}

        current_q = state.current_question
        next_q = current_q + 1 if current_q < 4 else None
        next_question_text = BUYER_QUESTIONS.get(next_q, "Let's lock in the details.")
        prompt = build_buyer_prompt(current_q, user_message, next_question_text)

        history = []
        for entry in state.conversation_history[-10:]:
            history.append({"role": "user", "content": entry["answer"]})
            bot_reply = entry.get("bot_response", "")
            if bot_reply:
                history.append({"role": "assistant", "content": bot_reply})

        try:
            llm_response = await self.claude_client.agenerate(
                prompt=prompt,
                system_prompt=BUYER_SYSTEM_PROMPT,
                history=history,
                max_tokens=400,
            )
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
            if bed_match:
                extracted["beds_min"] = int(bed_match.group(1))
            if bath_match:
                extracted["baths_min"] = float(bath_match.group(1))
            if sqft_match:
                extracted["sqft_min"] = int(sqft_match.group(1))

            # Price extraction: require explicit k-suffix, $-prefix, or 6+ digit bare numbers
            # to avoid matching zip codes (5 digits), bedroom counts, or sqft values
            k_prices = re.findall(r'\$?([\d,]+)\s*[kK]\b', msg)
            dollar_prices = re.findall(r'\$([\d,]+)\b', msg)
            bare_large = re.findall(r'\b(\d{6,})\b', msg) if not k_prices and not dollar_prices else []

            price_values = []
            for val in k_prices:
                price_values.append(int(val.replace(",", "")) * 1000)
            for val in dollar_prices:
                price_values.append(int(val.replace(",", "")))
            for val in bare_large:
                price_values.append(int(val))

            if price_values:
                if len(price_values) >= 2:
                    extracted["price_min"] = min(price_values)
                    extracted["price_max"] = max(price_values)
                else:
                    extracted["price_max"] = price_values[0]

            # location (simple heuristic)
            for area in JorgeBusinessRules.SERVICE_AREAS:
                if area.lower() in msg:
                    extracted["preferred_location"] = area
                    break

        elif question_num == 2:
            if any(phrase in msg for phrase in [
                "not approved", "not pre-approved", "not yet", "working on it",
                "haven't been", "havent been", "not pre approved"
            ]):
                extracted["preapproved"] = False
            elif any(word in msg for word in [
                "preapproved", "pre-approved", "pre approved", "approved", "cash", "yes"
            ]):
                extracted["preapproved"] = True
            elif any(word in msg for word in ["no", "nope"]):
                extracted["preapproved"] = False
            else:
                # Ambiguous answer (e.g. "still figuring it out") — treat as not approved,
                # but always advance so the conversation never stalls at Q2.
                extracted["preapproved"] = False

        elif question_num == 3:
            import re
            tl = None
            # Check "not interested in buying soon" phrases first (most specific)
            if any(phrase in msg for phrase in ["browsing", "just looking", "no rush", "not sure"]):
                tl = 180
            elif any(word in msg for word in ["asap", "immediately", "urgent", "right away"]):
                tl = 30
            elif "now" in msg.split():
                tl = 30
            elif "year" in msg:
                m = re.search(r"(\d+)\s*year", msg)
                tl = int(m.group(1)) * 365 if m else 365
            elif "month" in msg:
                m = re.search(r"(\d+)\s*-\s*(\d+)\s*month", msg)
                if m:
                    tl = int(m.group(1)) * 30
                else:
                    m = re.search(r"(\d+)\s*month", msg)
                    tl = int(m.group(1)) * 30 if m else 30
            elif "week" in msg:
                m = re.search(r"(\d+)\s*week", msg)
                tl = int(m.group(1)) * 7 if m else 14
            elif "day" in msg:
                m = re.search(r"(\d+)\s*-\s*(\d+)\s*day", msg)
                if m:
                    tl = int(m.group(2))
                else:
                    m = re.search(r"(\d+)\s*day", msg)
                    tl = int(m.group(1)) if m else 30
            else:
                m = re.search(r"\b([1-9][0-9]{0,2})\b", msg)
                if m:
                    n = int(m.group(1))
                    if 1 <= n <= 730:
                        tl = n
            extracted["timeline_days"] = tl if tl is not None else 90

        elif question_num == 4:
            motivations = {
                "job": "job_relocation",
                "relocation": "job_relocation",
                "relocating": "job_relocation",
                "moving": "job_relocation",
                "transfer": "job_relocation",
                "closer": "job_relocation",
                "military": "job_relocation",
                "family": "growing_family",
                "kids": "growing_family",
                "baby": "growing_family",
                "growing": "growing_family",
                "investment": "investment",
                "rental": "investment",
                "renting": "investment",
                "school": "school_district",
                "district": "school_district",
                "downsizing": "downsizing",
                "downsize": "downsizing",
                "retirement": "downsizing",
                "retiring": "downsizing",
                "upsizing": "upsizing",
                "upsize": "upsizing",
                "upgrade": "upsizing",
                "space": "upsizing",
                "room": "upsizing",
                "starter": "first_time_buyer",
                "first home": "first_time_buyer",
                "first-time": "first_time_buyer",
            }
            for keyword, value in motivations.items():
                if keyword in msg:
                    extracted["motivation"] = value
                    break
            if "motivation" not in extracted:
                extracted["motivation"] = "other"

        return extracted

    def _should_advance_question(self, extracted_data: Dict[str, Any], current_q: int) -> bool:
        if current_q == 1:
            # Require at least a price or bedroom/sqft count to advance — location name alone is insufficient
            return any(k in extracted_data for k in ["beds_min", "sqft_min", "price_max", "price_min"])
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

        for other_temp in [BuyerStatus.HOT, BuyerStatus.WARM, BuyerStatus.COLD]:
            if other_temp != temperature:
                actions.append({"type": "remove_tag", "tag": f"buyer_{other_temp}"})
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

        if settings.buyer_pipeline_id and not state.opportunity_created:
            actions.append({
                "type": "upsert_opportunity",
                "pipeline_id": settings.buyer_pipeline_id,
                "status": "qualified",
            })
            state.opportunity_created = True

        await self._apply_ghl_actions(contact_id, actions)
        return actions

    async def _apply_ghl_actions(self, contact_id: str, actions: List[Dict[str, Any]]) -> None:
        for action in actions:
            action_type = action.get("type")
            try:
                if action_type == "add_tag":
                    await self.ghl_client.add_tag(contact_id, action["tag"])
                elif action_type == "remove_tag":
                    await self.ghl_client.remove_tag(contact_id, action["tag"])
                elif action_type == "update_custom_field":
                    await self.ghl_client.update_custom_field(contact_id, action["field"], action["value"])
                elif action_type == "trigger_workflow":
                    await self.ghl_client.trigger_workflow(contact_id, action.get("workflow_id"))
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
        states: List[BuyerQualificationState] = []
        if not hasattr(self.cache, "smembers"):
            return []
        contact_ids = await self.cache.smembers("buyer:active_contacts")

        for contact_id in contact_ids:
            state_dict = await self.cache.get(f"buyer:state:{contact_id}")
            if not state_dict:
                continue
            state_data = state_dict.copy()
            if state_data.get("last_interaction"):
                state_data["last_interaction"] = datetime.fromisoformat(state_data["last_interaction"])
            if state_data.get("conversation_started"):
                state_data["conversation_started"] = datetime.fromisoformat(state_data["conversation_started"])
            valid_fields = {f.name for f in fields(BuyerQualificationState)}
            state_data = {k: v for k, v in state_data.items() if k in valid_fields}
            states.append(BuyerQualificationState(**state_data))

        return states


def create_buyer_bot(ghl_client: Optional[GHLClient] = None) -> JorgeBuyerBot:
    return JorgeBuyerBot(ghl_client=ghl_client)
