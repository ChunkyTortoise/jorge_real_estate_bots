"""
Lead Analyzer Service.

AI-powered lead qualification using Claude with Jorge's business rules.
Target: <500ms analysis time, >85% accuracy.
"""
from typing import Dict, Any, Optional
import json

from bots.shared.claude_client import ClaudeClient, TaskComplexity
from bots.shared.ghl_client import GHLClient
from bots.shared.cache_service import CacheService
from bots.shared.config import settings
from bots.shared.logger import get_logger

logger = get_logger(__name__)


class LeadAnalyzer:
    """
    Lead qualification engine with Claude AI.

    Analyzes leads against Jorge's criteria:
    - Price range: $200K-$800K
    - Service areas: Dallas, Plano, Frisco, McKinney, Allen
    - Timeline: Preferably <60 days
    - Buyer/Seller motivation assessment
    """

    def __init__(self):
        """Initialize Lead Analyzer with clients."""
        self.claude = ClaudeClient()
        self.ghl = GHLClient()
        self.cache = CacheService()

    async def analyze_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze lead and return score/temperature.

        Args:
            lead_data: GHL webhook payload with contact data

        Returns:
            Dict with score (0-100), temperature (hot/warm/cold), and analysis
        """
        contact_id = lead_data.get("id")
        logger.info(f"Analyzing lead: {contact_id}")

        # Extract relevant fields
        name = lead_data.get("name", "Unknown")
        email = lead_data.get("email", "")
        phone = lead_data.get("phone", "")
        source = lead_data.get("source", "Unknown")
        tags = lead_data.get("tags", [])
        custom_fields = lead_data.get("customField", {})

        # Build analysis prompt
        prompt = self._build_analysis_prompt(lead_data)

        # Call Claude AI for analysis (Target: <500ms)
        try:
            response = await self.claude.agenerate(
                prompt=prompt,
                system_prompt=self._get_system_prompt(),
                complexity=TaskComplexity.COMPLEX,  # Lead qualification is complex
                max_tokens=500,
                temperature=0.3,  # Low temperature for consistent scoring
                enable_caching=True  # Cache system prompt
            )

            # Parse response
            analysis = self._parse_claude_response(response.content)

            # Update GHL with results
            await self._update_ghl_fields(contact_id, analysis)

            # Send immediate follow-up based on temperature
            await self._send_followup(contact_id, analysis)

            return analysis

        except Exception as e:
            logger.error(f"Lead analysis error: {e}")
            # Fallback: Basic scoring without AI
            return self._fallback_scoring(lead_data)

    def _get_system_prompt(self) -> str:
        """
        Get system prompt for lead analysis.

        This prompt is cached by Claude (90% token savings on subsequent calls).
        """
        return f"""You are Jorge's AI Lead Qualification Assistant for real estate.

**Jorge's Business Rules:**
- Price Range: ${settings.jorge_min_price:,} - ${settings.jorge_max_price:,}
- Service Areas: {settings.jorge_service_areas}
- Preferred Timeline: {settings.jorge_preferred_timeline} days or less
- Commission: {settings.jorge_standard_commission * 100}% (negotiable to {settings.jorge_minimum_commission * 100}%)

**Lead Scoring Criteria (0-100):**

1. **Price Range Match (30 points)**
   - Within range: 30 points
   - Slightly outside: 20 points
   - Way outside: 0 points

2. **Location (25 points)**
   - In service area: 25 points
   - Adjacent area: 15 points
   - Outside: 0 points

3. **Timeline/Urgency (20 points)**
   - ASAP/30 days: 20 points
   - 60-90 days: 15 points
   - 6+ months: 5 points

4. **Buyer Motivation (15 points)**
   - Strong signals (pre-approved, selling home): 15 points
   - Medium (actively looking): 10 points
   - Weak (just browsing): 5 points

5. **Contact Quality (10 points)**
   - Full contact info + specific needs: 10 points
   - Partial info: 5 points
   - Minimal: 2 points

**Temperature Assignment:**
- **HOT (80-100)**: Immediate call within 1 hour
- **WARM (60-79)**: Follow up within 24 hours
- **COLD (0-59)**: Add to nurture sequence

**Response Format (JSON):**
{{
  "score": <0-100>,
  "temperature": "hot|warm|cold",
  "reasoning": "Brief explanation",
  "action": "Recommended next step",
  "budget_estimate": "<min-max range or null>",
  "timeline_estimate": "<days or null>"
}}

Be concise. Focus on actionable insights for Jorge."""

    def _build_analysis_prompt(self, lead_data: Dict[str, Any]) -> str:
        """Build analysis prompt from lead data."""
        name = lead_data.get("name", "Unknown")
        email = lead_data.get("email", "")
        phone = lead_data.get("phone", "")
        source = lead_data.get("source", "Unknown")
        tags = lead_data.get("tags", [])
        custom_fields = lead_data.get("customField", {})

        prompt = f"""Analyze this lead:

**Contact:**
- Name: {name}
- Email: {email}
- Phone: {phone}
- Source: {source}
- Tags: {', '.join(tags) if tags else 'None'}

**Custom Fields:**
"""
        for key, value in custom_fields.items():
            prompt += f"- {key}: {value}\n"

        prompt += "\nProvide lead score, temperature, and recommended action in JSON format."

        return prompt

    def _parse_claude_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's JSON response."""
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                analysis = json.loads(response_text)

            # Validate required fields
            score = int(analysis.get("score", 50))
            temperature = analysis.get("temperature", "warm").lower()

            # Ensure temperature is valid
            if temperature not in ["hot", "warm", "cold"]:
                temperature = "warm"

            return {
                "score": max(0, min(100, score)),  # Clamp to 0-100
                "temperature": temperature,
                "reasoning": analysis.get("reasoning", ""),
                "action": analysis.get("action", ""),
                "budget_estimate": analysis.get("budget_estimate"),
                "timeline_estimate": analysis.get("timeline_estimate")
            }

        except Exception as e:
            logger.error(f"Failed to parse Claude response: {e}")
            # Fallback to default
            return {
                "score": 50,
                "temperature": "warm",
                "reasoning": "Error parsing AI response",
                "action": "Manual review required",
                "budget_estimate": None,
                "timeline_estimate": None
            }

    async def _update_ghl_fields(self, contact_id: str, analysis: Dict[str, Any]):
        """Update GHL custom fields with analysis results."""
        try:
            result = await self._async_ghl_update(contact_id, analysis)
            if result.get("success"):
                logger.info(f"✅ Updated GHL fields for {contact_id}")
            else:
                logger.warning(f"⚠️ GHL update failed: {result.get('error')}")
        except Exception as e:
            logger.error(f"GHL update error: {e}")

    async def _async_ghl_update(self, contact_id: str, analysis: Dict[str, Any]) -> Dict:
        """Async wrapper for GHL update (sync library)."""
        import asyncio
        return await asyncio.to_thread(
            self.ghl.update_lead_score,
            contact_id,
            analysis["score"],
            analysis["temperature"]
        )

    async def _send_followup(self, contact_id: str, analysis: Dict[str, Any]):
        """Send immediate follow-up based on lead temperature."""
        try:
            temperature = analysis["temperature"]
            result = await self._async_send_followup(contact_id, temperature)
            if result.get("success"):
                logger.info(f"📬 Follow-up sent for {contact_id} ({temperature})")
        except Exception as e:
            logger.error(f"Follow-up error: {e}")

    async def _async_send_followup(self, contact_id: str, temperature: str) -> Dict:
        """Async wrapper for sending follow-up."""
        import asyncio
        return await asyncio.to_thread(
            self.ghl.send_immediate_followup,
            contact_id,
            temperature
        )

    def _fallback_scoring(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback scoring if AI fails.

        Simple rule-based scoring for reliability.
        """
        score = 50  # Default medium
        temperature = "warm"

        # Check if we have basic contact info
        has_email = bool(lead_data.get("email"))
        has_phone = bool(lead_data.get("phone"))

        if has_email and has_phone:
            score = 60
        elif has_email or has_phone:
            score = 50
        else:
            score = 30
            temperature = "cold"

        return {
            "score": score,
            "temperature": temperature,
            "reasoning": "Fallback scoring (AI unavailable)",
            "action": "Manual review required",
            "budget_estimate": None,
            "timeline_estimate": None
        }
