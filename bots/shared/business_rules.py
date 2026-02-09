"""
Jorge's Business Rules for Real Estate Lead Qualification.

Contains Jorge's specific business logic for:
- Budget validation ($200K-$800K range)
- Service area validation (Dallas Metro)
- Lead priority assignment
- Commission calculation (6% standard)
- Timeline preferences

Extracted from jorge_deployment_package/jorge_claude_intelligence.py
"""
from dataclasses import dataclass
from typing import Any, Dict, List

from bots.shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class JorgeBusinessRules:
    """
    Jorge's specific business rules for lead qualification.

    Business Parameters:
    - Budget Range: $200K - $800K (sweet spot)
    - Service Areas: Dallas, Plano, Frisco, McKinney, Allen
    - Timeline: 60 days preferred, 30 days urgent
    - Commission: 6% standard rate
    - Hot Lead: Score >= 80
    - Warm Lead: Score >= 60
    """

    # Price range validation
    MIN_BUDGET = 200000  # $200K minimum
    MAX_BUDGET = 800000  # $800K maximum

    # Service areas (Dallas Metro)
    SERVICE_AREAS = ["Dallas", "Plano", "Frisco", "McKinney", "Allen"]

    # Timeline preferences (in days)
    PREFERRED_TIMELINE = "60_days"
    URGENT_TIMELINE = "30_days"

    # Lead quality thresholds
    HOT_LEAD_THRESHOLD = 80
    WARM_LEAD_THRESHOLD = 60

    # Commission rates
    STANDARD_COMMISSION_RATE = 0.06  # 6%

    @classmethod
    def validate_lead(cls, lead_data: Dict) -> Dict[str, Any]:
        """
        Validate lead against Jorge's business rules.

        Args:
            lead_data: Dictionary containing lead information:
                - budget_max: Maximum budget (int)
                - location_preferences: List of preferred locations
                - timeline: Timeline string (optional)

        Returns:
            Dictionary with validation results:
                - passes_jorge_criteria: bool
                - validation_issues: List[str]
                - jorge_priority: str ("high", "normal", "review_required")
                - estimated_commission: float
                - service_area_match: bool
        """
        validation_results = {
            "passes_jorge_criteria": True,
            "validation_issues": [],
            "jorge_priority": "normal",
            "estimated_commission": 0.0,
            "service_area_match": False
        }

        # Budget validation
        budget_max = lead_data.get("budget_max", 0)
        if budget_max and budget_max < cls.MIN_BUDGET:
            validation_results["passes_jorge_criteria"] = False
            validation_results["validation_issues"].append(
                f"Budget too low: ${budget_max:,} < ${cls.MIN_BUDGET:,}"
            )
            logger.debug(f"Lead failed: budget ${budget_max:,} below minimum ${cls.MIN_BUDGET:,}")

        if budget_max and budget_max > cls.MAX_BUDGET:
            validation_results["jorge_priority"] = "review_required"
            validation_results["validation_issues"].append(
                f"Budget above target: ${budget_max:,} > ${cls.MAX_BUDGET:,}"
            )
            logger.debug(f"Lead requires review: budget ${budget_max:,} above target ${cls.MAX_BUDGET:,}")

        # Service area validation
        location_preferences = lead_data.get("location_preferences", [])
        if isinstance(location_preferences, list):
            location_text = " ".join(location_preferences).lower()
        else:
            location_text = str(location_preferences).lower()

        for area in cls.SERVICE_AREAS:
            if area.lower() in location_text:
                validation_results["service_area_match"] = True
                logger.debug(f"Service area match found: {area}")
                break

        # Calculate estimated commission (6% of budget)
        if budget_max:
            validation_results["estimated_commission"] = budget_max * cls.STANDARD_COMMISSION_RATE
            logger.debug(f"Estimated commission: ${validation_results['estimated_commission']:,.2f}")

        # Set priority based on Jorge's criteria
        if (budget_max and
            cls.MIN_BUDGET <= budget_max <= cls.MAX_BUDGET and
            validation_results["service_area_match"]):
            validation_results["jorge_priority"] = "high"
            logger.info(f"High priority lead: budget ${budget_max:,}, service area match")

        return validation_results

    @classmethod
    def get_temperature(cls, lead_score: float) -> str:
        """
        Convert lead score to temperature category.

        Args:
            lead_score: Numeric lead score (0-100)

        Returns:
            Temperature string: "hot", "warm", or "cold"
        """
        if lead_score >= cls.HOT_LEAD_THRESHOLD:
            return "hot"
        elif lead_score >= cls.WARM_LEAD_THRESHOLD:
            return "warm"
        else:
            return "cold"

    @classmethod
    def is_hot_lead(cls, lead_score: float) -> bool:
        """Check if lead qualifies as hot (>=80)"""
        return lead_score >= cls.HOT_LEAD_THRESHOLD

    @classmethod
    def is_qualified_lead(cls, lead_data: Dict) -> bool:
        """
        Check if lead meets minimum qualification criteria.

        Args:
            lead_data: Lead information dictionary

        Returns:
            True if lead passes Jorge's criteria
        """
        validation = cls.validate_lead(lead_data)
        return validation["passes_jorge_criteria"]

    @classmethod
    def calculate_commission(cls, budget: float, rate: float = None) -> float:
        """
        Calculate commission for a given budget.

        Args:
            budget: Property budget
            rate: Commission rate (defaults to standard 6%)

        Returns:
            Commission amount in dollars
        """
        if rate is None:
            rate = cls.STANDARD_COMMISSION_RATE
        return budget * rate

    @classmethod
    def get_service_areas(cls) -> List[str]:
        """Get list of Jorge's service areas."""
        return cls.SERVICE_AREAS.copy()

    @classmethod
    def is_service_area(cls, location: str) -> bool:
        """Check if location is in Jorge's service areas."""
        location_lower = location.lower()
        return any(area.lower() in location_lower for area in cls.SERVICE_AREAS)
