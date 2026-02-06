"""
Optimized Lead Intelligence - Pattern-Based Scoring

Fast, AI-free lead scoring system using keyword patterns and business rules.
Provides <100ms fallback when AI is unavailable or for simple leads.

Extracted from jorge_deployment_package/lead_intelligence_optimized.py
Integrated into jorge_real_estate_bots MVP.

Author: Claude Code Assistant
Created: 2026-01-23
"""
import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class EnhancedLeadProfile:
    """Enhanced lead profile with robust data handling"""

    # Core data with defaults
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    timeline: str = "unknown"
    location_preferences: List[str] = field(default_factory=list)
    financing_status: str = "unknown"

    # Derived metrics
    urgency_score: float = 0.0
    qualification_score: float = 0.0
    intent_confidence: float = 0.0

    # Quality indicators
    has_specific_budget: bool = False
    has_clear_timeline: bool = False
    has_location_preference: bool = False
    is_pre_approved: bool = False

    # Error tracking
    parsing_errors: List[str] = field(default_factory=list)
    fallback_used: bool = False


class PredictiveLeadScorerV2Optimized:
    """
    Optimized lead scorer with pattern-based keyword extraction.

    No AI calls - pure regex and business logic for <100ms performance.
    Ideal for fallback scoring when AI is unavailable or rate-limited.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Enhanced budget patterns for Dallas market
        self.budget_patterns = [
            r'\$([0-9]{1,3}(?:,?[0-9]{3})*?)k\b',  # $500k, $1,000k
            r'\$([0-9]{1,3}(?:,?[0-9]{3})*?),?000\b',  # $500,000
            r'([0-9]{1,3}(?:,?[0-9]{3})*?)k budget',  # 500k budget
            r'under \$([0-9]{1,3}(?:,?[0-9]{3})*?)k?',  # under $500k
            r'up to \$([0-9]{1,3}(?:,?[0-9]{3})*?)k?',  # up to $500
            r'around \$([0-9]{1,3}(?:,?[0-9]{3})*?)k?',  # around $500k
            r'budget.*?\$([0-9]{1,3}(?:,?[0-9]{3})*?)k?',  # budget of $500k
        ]

        self.timeline_keywords = {
            "immediate": ["immediately", "asap", "right now", "urgent", "today", "this week"],
            "1_month": ["month", "30 days", "within a month", "4 weeks"],
            "2_months": ["2 months", "60 days", "couple months", "8 weeks"],
            "3_months": ["3 months", "90 days", "quarter", "12 weeks"],
            "6_months": ["6 months", "half year", "by summer", "by winter"],
            "1_year": ["year", "12 months", "annual", "eventually"],
            "flexible": ["flexible", "no rush", "whenever", "someday", "maybe"]
        }

        # Dallas metro area locations
        self.location_keywords = {
            # Core cities
            "dallas": ["dallas", "downtown dallas"],
            "plano": ["plano"],
            "frisco": ["frisco"],
            "mckinney": ["mckinney"],
            "allen": ["allen"],

            # Additional Dallas metro areas
            "richardson": ["richardson"],
            "garland": ["garland"],
            "irving": ["irving"],
            "arlington": ["arlington"],
            "fort_worth": ["fort worth", "fortworth"],
            "mesquite": ["mesquite"],
            "carrollton": ["carrollton"],
            "denton": ["denton"],
            "lewisville": ["lewisville"],
            "flower_mound": ["flower mound"],

            # Premium areas
            "highland_park": ["highland park"],
            "university_park": ["university park"],
            "southlake": ["southlake"],
            "colleyville": ["colleyville"],

            # Specific neighborhoods
            "uptown": ["uptown", "uptown dallas"],
            "deep_ellum": ["deep ellum"],
            "bishop_arts": ["bishop arts"],
            "lakewood": ["lakewood"],
        }

        self.financing_keywords = {
            "cash": ["cash", "cash buyer", "all cash", "no financing", "no loan"],
            "pre_approved": [
                "pre-approved", "preapproved", "pre approved", "already approved",
                "bank approved", "lender approved", "loan approved", "financing approved"
            ],
            "conventional": ["conventional loan", "conventional financing"],
            "fha": ["fha", "fha loan"],
            "va": ["va loan", "va financing", "veteran"],
            "jumbo": ["jumbo loan", "jumbo financing"],
            "needs_financing": ["need financing", "need a loan", "getting approved", "applying for loan"]
        }

    def analyze_lead_message(self, message: str) -> EnhancedLeadProfile:
        """
        Enhanced lead analysis with comprehensive error handling.

        Args:
            message: Lead message/notes from GHL webhook

        Returns:
            EnhancedLeadProfile with scores and extracted data
        """
        if not message or not isinstance(message, str):
            self.logger.warning("Invalid message input for lead analysis")
            return self._create_fallback_profile("Invalid message input")

        try:
            profile = EnhancedLeadProfile()
            message_clean = message.lower().strip()

            if not message_clean:
                return self._create_fallback_profile("Empty message")

            # Extract budget with error handling
            try:
                profile.budget_min, profile.budget_max = self._extract_budget_safe(message_clean)
                profile.has_specific_budget = profile.budget_max is not None
            except Exception as e:
                profile.parsing_errors.append(f"Budget extraction: {str(e)}")
                self.logger.warning(f"Budget extraction error: {e}")

            # Extract timeline with error handling
            try:
                profile.timeline = self._extract_timeline_safe(message_clean)
                profile.has_clear_timeline = profile.timeline != "unknown"
            except Exception as e:
                profile.parsing_errors.append(f"Timeline extraction: {str(e)}")
                self.logger.warning(f"Timeline extraction error: {e}")

            # Extract location with error handling
            try:
                profile.location_preferences = self._extract_locations_safe(message_clean)
                profile.has_location_preference = len(profile.location_preferences) > 0
            except Exception as e:
                profile.parsing_errors.append(f"Location extraction: {str(e)}")
                self.logger.warning(f"Location extraction error: {e}")

            # Extract financing status with error handling
            try:
                profile.financing_status = self._extract_financing_safe(message_clean)
                profile.is_pre_approved = profile.financing_status == "pre_approved"
            except Exception as e:
                profile.parsing_errors.append(f"Financing extraction: {str(e)}")
                self.logger.warning(f"Financing extraction error: {e}")

            # Calculate scores with error handling
            try:
                profile.urgency_score = self._calculate_urgency_score_safe(message_clean, profile)
                profile.qualification_score = self._calculate_qualification_score_safe(profile)
                profile.intent_confidence = self._calculate_intent_confidence_safe(message_clean, profile)
            except Exception as e:
                profile.parsing_errors.append(f"Score calculation: {str(e)}")
                self.logger.warning(f"Score calculation error: {e}")
                # Use fallback scores
                profile.urgency_score = 0.3
                profile.qualification_score = 0.3
                profile.intent_confidence = 0.3

            return profile

        except Exception as e:
            self.logger.error(f"Critical lead analysis error: {e}")
            return self._create_fallback_profile(f"Analysis failed: {str(e)}")

    def _extract_budget_safe(self, message: str) -> tuple[Optional[int], Optional[int]]:
        """Safely extract budget information"""
        if not message:
            return None, None

        try:
            for pattern in self.budget_patterns:
                matches = re.findall(pattern, message, re.IGNORECASE)
                if matches:
                    for match in matches:
                        try:
                            # Clean the match
                            amount_str = str(match).replace(',', '')
                            amount = int(amount_str)

                            # Handle 'k' suffix
                            if 'k' in pattern.lower():
                                amount *= 1000

                            # Reasonable range check (Dallas market)
                            if 50000 <= amount <= 5000000:  # $50k to $5M reasonable range
                                # For "under" or "up to", use as max budget
                                if any(phrase in message for phrase in ["under", "up to", "max"]):
                                    return None, amount
                                else:
                                    return amount, amount  # Exact budget
                        except (ValueError, TypeError) as e:
                            self.logger.debug(f"Budget parsing error for match '{match}': {e}")
                            continue

            return None, None

        except Exception as e:
            self.logger.warning(f"Budget extraction failed: {e}")
            return None, None

    def _extract_timeline_safe(self, message: str) -> str:
        """Safely extract timeline information"""
        if not message:
            return "unknown"

        try:
            for timeline, keywords in self.timeline_keywords.items():
                if any(keyword in message for keyword in keywords):
                    return timeline

            # Check for numeric patterns like "30 days", "6 weeks"
            time_patterns = [
                (r'(\d+)\s*days?', lambda x: "immediate" if int(x) <= 7 else "1_month" if int(x) <= 30 else "2_months"),
                (r'(\d+)\s*weeks?', lambda x: "immediate" if int(x) <= 1 else "1_month" if int(x) <= 4 else "2_months"),
                (r'(\d+)\s*months?', lambda x: "1_month" if int(x) <= 1 else "2_months" if int(x) <= 2 else "3_months")
            ]

            for pattern, categorizer in time_patterns:
                match = re.search(pattern, message)
                if match:
                    try:
                        number = int(match.group(1))
                        return categorizer(str(number))
                    except (ValueError, TypeError):
                        continue

            return "unknown"

        except Exception as e:
            self.logger.warning(f"Timeline extraction failed: {e}")
            return "unknown"

    def _extract_locations_safe(self, message: str) -> List[str]:
        """Safely extract location preferences"""
        if not message:
            return []

        try:
            found_locations = []

            for location_category, keywords in self.location_keywords.items():
                for keyword in keywords:
                    if keyword in message:
                        # Convert to readable format
                        readable_name = location_category.replace('_', ' ').title()
                        if readable_name not in found_locations:
                            found_locations.append(readable_name)

            return found_locations[:3]  # Limit to top 3 to avoid clutter

        except Exception as e:
            self.logger.warning(f"Location extraction failed: {e}")
            return []

    def _extract_financing_safe(self, message: str) -> str:
        """Safely extract financing status"""
        if not message:
            return "unknown"

        try:
            for financing_type, keywords in self.financing_keywords.items():
                if any(keyword in message for keyword in keywords):
                    return financing_type

            return "unknown"

        except Exception as e:
            self.logger.warning(f"Financing extraction failed: {e}")
            return "unknown"

    def _calculate_urgency_score_safe(self, message: str, profile: EnhancedLeadProfile) -> float:
        """Safely calculate urgency score (0.0-1.0)"""
        try:
            score = 0.0

            if not message:
                return 0.0

            # Timeline urgency
            timeline_scores = {
                "immediate": 1.0,
                "1_month": 0.8,
                "2_months": 0.6,
                "3_months": 0.4,
                "6_months": 0.2,
                "1_year": 0.1,
                "flexible": 0.0
            }
            score += timeline_scores.get(profile.timeline, 0.0) * 0.4

            # Urgent keywords
            urgent_keywords = [
                "asap", "urgent", "immediately", "quickly", "fast",
                "need to", "have to", "must", "deadline"
            ]
            urgency_mentions = sum(1 for keyword in urgent_keywords if keyword in message)
            score += min(urgency_mentions * 0.1, 0.3)

            # Financing readiness
            if profile.financing_status in ["cash", "pre_approved"]:
                score += 0.3

            return min(1.0, score)

        except Exception as e:
            self.logger.warning(f"Urgency score calculation failed: {e}")
            return 0.3  # Safe fallback

    def _calculate_qualification_score_safe(self, profile: EnhancedLeadProfile) -> float:
        """Safely calculate qualification score (0.0-1.0)"""
        try:
            score = 0.0

            # Budget qualification
            if profile.has_specific_budget:
                score += 0.3
                if profile.budget_max and profile.budget_max >= 300000:
                    score += 0.1  # Bonus for substantial budget

            # Timeline qualification
            if profile.has_clear_timeline and profile.timeline != "flexible":
                score += 0.2

            # Location qualification
            if profile.has_location_preference:
                score += 0.2

            # Financing qualification
            if profile.financing_status in ["cash", "pre_approved"]:
                score += 0.3
            elif profile.financing_status != "unknown":
                score += 0.1

            return min(1.0, score)

        except Exception as e:
            self.logger.warning(f"Qualification score calculation failed: {e}")
            return 0.3  # Safe fallback

    def _calculate_intent_confidence_safe(self, message: str, profile: EnhancedLeadProfile) -> float:
        """Safely calculate intent confidence (0.0-1.0)"""
        try:
            score = 0.0

            if not message:
                return 0.0

            # Message length and detail
            if len(message) > 100:
                score += 0.2
            elif len(message) > 50:
                score += 0.1

            # Specific details provided
            details_count = sum([
                profile.has_specific_budget,
                profile.has_clear_timeline,
                profile.has_location_preference,
                profile.is_pre_approved
            ])
            score += details_count * 0.15

            # Intent keywords
            intent_keywords = [
                "looking for", "want to buy", "ready to buy", "need a house",
                "searching for", "help me find", "show me", "interested in"
            ]
            intent_mentions = sum(1 for keyword in intent_keywords if keyword in message)
            score += min(intent_mentions * 0.1, 0.2)

            # Question marks (engagement)
            questions = message.count('?')
            score += min(questions * 0.05, 0.1)

            return min(1.0, score)

        except Exception as e:
            self.logger.warning(f"Intent confidence calculation failed: {e}")
            return 0.3  # Safe fallback

    def _create_fallback_profile(self, error_msg: str) -> EnhancedLeadProfile:
        """Create a safe fallback profile when analysis fails"""
        profile = EnhancedLeadProfile()
        profile.fallback_used = True
        profile.parsing_errors = [error_msg]
        profile.urgency_score = 0.3
        profile.qualification_score = 0.3
        profile.intent_confidence = 0.3

        return profile


def get_enhanced_lead_intelligence(message: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Enhanced lead intelligence function with comprehensive error handling.

    Main entry point for pattern-based lead scoring.
    No AI calls - pure keyword extraction and business logic.

    Args:
        message: Lead message/notes from GHL webhook
        context: Optional context (not used in pattern-based scoring)

    Returns:
        Dict with lead score, urgency, qualification, and extracted details
    """
    if not message:
        logger.warning("Empty message provided to lead intelligence")
        return {
            "lead_score": 30.0,
            "urgency": 0.3,
            "qualification": 0.3,
            "intent_confidence": 0.3,
            "budget_analysis": "unknown",
            "timeline_analysis": "unknown",
            "location_analysis": [],
            "financing_analysis": "unknown",
            "errors": ["Empty message"],
            "fallback_used": True
        }

    try:
        scorer = PredictiveLeadScorerV2Optimized()
        profile = scorer.analyze_lead_message(message)

        # Calculate overall lead score (0-100) - OPTIMIZED SCORING
        base_score = 35.0  # Slightly higher minimum score
        qualification_bonus = profile.qualification_score * 45  # Up to 45 points
        urgency_bonus = profile.urgency_score * 15  # Up to 15 points
        intent_bonus = profile.intent_confidence * 5  # Up to 5 points

        total_score = base_score + qualification_bonus + urgency_bonus + intent_bonus

        # Budget analysis
        budget_analysis = "unknown"
        if profile.budget_max:
            if profile.budget_max >= 500000:
                budget_analysis = "high"
            elif profile.budget_max >= 300000:
                budget_analysis = "medium"
            else:
                budget_analysis = "budget_conscious"

        return {
            "lead_score": round(min(100.0, total_score), 1),
            "urgency": round(profile.urgency_score, 2),
            "qualification": round(profile.qualification_score, 2),
            "intent_confidence": round(profile.intent_confidence, 2),
            "budget_analysis": budget_analysis,
            "timeline_analysis": profile.timeline,
            "location_analysis": profile.location_preferences,
            "financing_analysis": profile.financing_status,
            "budget_max": profile.budget_max,
            "has_specific_budget": profile.has_specific_budget,
            "has_clear_timeline": profile.has_clear_timeline,
            "has_location_preference": profile.has_location_preference,
            "is_pre_approved": profile.is_pre_approved,
            "errors": profile.parsing_errors,
            "fallback_used": profile.fallback_used
        }

    except Exception as e:
        logger.error(f"Critical error in lead intelligence: {e}")
        return {
            "lead_score": 30.0,
            "urgency": 0.3,
            "qualification": 0.3,
            "intent_confidence": 0.3,
            "budget_analysis": "unknown",
            "timeline_analysis": "unknown",
            "location_analysis": [],
            "financing_analysis": "unknown",
            "errors": [f"Critical error: {str(e)}"],
            "fallback_used": True
        }
