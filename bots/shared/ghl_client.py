"""
GoHighLevel API Client for Jorge's Real Estate Bots.

Simplified wrapper for GHL API v2 focused on Jorge's workflows.
Adapted from EnterpriseHub with Jorge-specific methods.
"""
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from bots.shared.config import settings
from bots.shared.logger import get_logger

logger = get_logger(__name__)


class GHLClient:
    """
    GoHighLevel API Client for real estate automation.

    Provides methods for:
    - Contact/Lead management
    - Opportunity/Deal management
    - Custom field updates
    - Message sending (SMS/Email)
    - Pipeline management
    """

    BASE_URL = "https://services.leadconnectorhq.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        location_id: Optional[str] = None
    ):
        """
        Initialize GHL API Client.

        Args:
            api_key: GHL API key (defaults to settings)
            location_id: GHL Location ID (defaults to settings)
        """
        self.api_key = api_key or settings.ghl_api_key
        self.location_id = location_id or settings.ghl_location_id

        if not self.api_key:
            raise ValueError("GHL_API_KEY is required")
        if not self.location_id:
            raise ValueError("GHL_LOCATION_ID is required")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Version": "2021-07-28",
            "Content-Type": "application/json"
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Make API request to GHL.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            data: Request body data
            params: Query parameters

        Returns:
            API response as dictionary
        """
        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=30
            )

            response.raise_for_status()

            return {
                "success": True,
                "data": response.json() if response.content else {},
                "status_code": response.status_code
            }

        except requests.exceptions.HTTPError as e:
            logger.error(f"GHL API error: {e}")
            return {
                "success": False,
                "error": str(e),
                "status_code": e.response.status_code if hasattr(e, 'response') else 500,
                "details": e.response.json() if hasattr(e, 'response') and e.response.content else {}
            }
        except Exception as e:
            logger.error(f"GHL request error: {e}")
            return {
                "success": False,
                "error": str(e),
                "status_code": 500
            }

    # ========== CONTACTS/LEADS ==========

    def get_contact(self, contact_id: str) -> Dict:
        """Get single contact by ID."""
        return self._make_request("GET", f"contacts/{contact_id}")

    def create_contact(self, contact_data: Dict) -> Dict:
        """Create new contact in GHL."""
        contact_data["locationId"] = self.location_id
        return self._make_request("POST", "contacts", data=contact_data)

    def update_contact(self, contact_id: str, updates: Dict) -> Dict:
        """Update contact information."""
        return self._make_request("PUT", f"contacts/{contact_id}", data=updates)

    def add_tag_to_contact(self, contact_id: str, tag: str) -> Dict:
        """Add tag to contact."""
        return self._make_request(
            "POST",
            f"contacts/{contact_id}/tags",
            data={"tags": [tag]}
        )

    # ========== CUSTOM FIELDS ==========

    def update_custom_field(
        self,
        contact_id: str,
        field_key: str,
        field_value: Any
    ) -> Dict:
        """
        Update custom field value for contact.

        Jorge's Custom Fields:
        - ai_lead_score: 0-100
        - lead_temperature: hot/warm/cold
        - budget_min: number
        - budget_max: number
        - timeline: string
        - financing_status: string
        """
        return self.update_contact(contact_id, {
            "customField": {field_key: field_value}
        })

    # ========== OPPORTUNITIES ==========

    def create_opportunity(self, opportunity_data: Dict) -> Dict:
        """Create new opportunity."""
        opportunity_data["locationId"] = self.location_id
        return self._make_request("POST", "opportunities", data=opportunity_data)

    def update_opportunity(self, opportunity_id: str, updates: Dict) -> Dict:
        """Update opportunity."""
        return self._make_request("PUT", f"opportunities/{opportunity_id}", data=updates)

    # ========== MESSAGING ==========

    def send_message(
        self,
        contact_id: str,
        message: str,
        message_type: str = "SMS"
    ) -> Dict:
        """
        Send message to contact.

        Args:
            contact_id: GHL Contact ID
            message: Message text
            message_type: SMS or Email
        """
        data = {
            "contactId": contact_id,
            "message": message,
            "type": message_type
        }
        return self._make_request("POST", "conversations/messages", data=data)

    # ========== JORGE-SPECIFIC METHODS ==========

    def update_lead_score(
        self,
        contact_id: str,
        score: int,
        temperature: str
    ) -> Dict:
        """
        Update lead score and temperature (Jorge's key metrics).

        Args:
            contact_id: GHL Contact ID
            score: Lead score 0-100
            temperature: hot, warm, or cold

        Returns:
            Update result
        """
        return self.update_contact(contact_id, {
            "customField": {
                "ai_lead_score": score,
                "lead_temperature": temperature
            }
        })

    def update_budget_and_timeline(
        self,
        contact_id: str,
        budget_min: Optional[int] = None,
        budget_max: Optional[int] = None,
        timeline: Optional[str] = None
    ) -> Dict:
        """
        Update lead budget and timeline.

        Args:
            contact_id: GHL Contact ID
            budget_min: Minimum budget
            budget_max: Maximum budget
            timeline: Timeline (e.g., "ASAP", "30", "60", "90", "180+")
        """
        custom_fields = {}
        if budget_min is not None:
            custom_fields["budget_min"] = budget_min
        if budget_max is not None:
            custom_fields["budget_max"] = budget_max
        if timeline:
            custom_fields["timeline"] = timeline

        return self.update_contact(contact_id, {
            "customField": custom_fields
        })

    def send_immediate_followup(
        self,
        contact_id: str,
        lead_temperature: str
    ) -> Dict:
        """
        Send immediate follow-up based on lead temperature.

        Hot leads: Immediate call task
        Warm leads: 24hr follow-up
        Cold leads: Weekly nurture
        """
        if lead_temperature == "hot":
            message = f"🔥 HOT LEAD ALERT! Contact immediately for {contact_id}"
        elif lead_temperature == "warm":
            message = f"⚠️ WARM LEAD: Follow up within 24 hours for {contact_id}"
        else:
            message = f"📊 COLD LEAD: Added to nurture sequence for {contact_id}"

        # Send SMS notification to Jorge
        return self.send_message(
            contact_id=contact_id,
            message=message,
            message_type="SMS"
        )

    def health_check(self) -> Dict:
        """
        Check API connection health.

        Returns:
            Health status
        """
        try:
            result = self._make_request("GET", "contacts", params={"limit": 1, "locationId": self.location_id})
            return {
                "healthy": result.get("success", False),
                "api_key_valid": result.get("success", False),
                "location_id": self.location_id,
                "checked_at": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }


# Global client instance
def get_ghl_client() -> GHLClient:
    """Get a GHL client instance."""
    return GHLClient()
