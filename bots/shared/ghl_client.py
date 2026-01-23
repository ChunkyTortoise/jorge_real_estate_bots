"""
GoHighLevel API Client for Jorge's Real Estate Bots.

Production-grade async wrapper for GHL API v2 with comprehensive coverage.
Integrated from jorge_deployment_package with enhanced error handling and retry logic.

Features:
- Async/await support with httpx
- Contact and opportunity management
- Conversation and messaging
- Workflow automation
- Calendar appointments
- Custom field updates
- Tag management
- Batch operations
- Health monitoring
"""
import httpx
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from bots.shared.config import settings
from bots.shared.logger import get_logger

logger = get_logger(__name__)


class GHLClient:
    """
    Production-grade GoHighLevel API Client for real estate automation.

    Provides comprehensive GHL API coverage:
    - Contact/Lead management
    - Opportunity/Deal management
    - Conversation handling
    - Message sending (SMS/Email)
    - Workflow triggering
    - Calendar appointments
    - Custom field updates
    - Tag management
    - Batch operations
    - Health monitoring

    Uses async/await for performance and retry logic for reliability.
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
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError))
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Make async API request to GHL with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            data: Request body data
            params: Query parameters

        Returns:
            API response as dictionary
        """
        url = f"{self.BASE_URL}/{endpoint}"
        client = self._get_client()

        try:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params
            )

            response.raise_for_status()

            return {
                "success": True,
                "data": response.json() if response.content else {},
                "status_code": response.status_code
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"GHL API HTTP error: {e.response.status_code} - {e}")
            return {
                "success": False,
                "error": str(e),
                "status_code": e.response.status_code,
                "details": e.response.json() if e.response.content else {}
            }
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            logger.error(f"GHL network/timeout error: {e}")
            raise  # Retry these
        except Exception as e:
            logger.error(f"GHL request error: {e}")
            return {
                "success": False,
                "error": str(e),
                "status_code": 500
            }

    # ========== CONTACTS/LEADS ==========

    async def get_contact(self, contact_id: str) -> Dict:
        """Get single contact by ID."""
        return await self._make_request("GET", f"contacts/{contact_id}")

    async def create_contact(self, contact_data: Dict) -> Dict:
        """Create new contact in GHL."""
        contact_data["locationId"] = self.location_id
        return await self._make_request("POST", "contacts", data=contact_data)

    async def update_contact(self, contact_id: str, updates: Dict) -> Dict:
        """Update contact information."""
        return await self._make_request("PUT", f"contacts/{contact_id}", data=updates)

    async def add_tag(self, contact_id: str, tag: str) -> bool:
        """Add tag to contact."""
        result = await self._make_request(
            "POST",
            f"contacts/{contact_id}/tags",
            data={"tags": [tag]}
        )
        return result.get("success", False)

    async def add_tag_to_contact(self, contact_id: str, tag: str) -> Dict:
        """Add tag to contact (legacy method for backwards compatibility)."""
        return await self._make_request(
            "POST",
            f"contacts/{contact_id}/tags",
            data={"tags": [tag]}
        )

    async def remove_tag(self, contact_id: str, tag: str) -> bool:
        """Remove tag from contact."""
        result = await self._make_request(
            "DELETE",
            f"contacts/{contact_id}/tags/{tag}"
        )
        return result.get("success", False)

    # ========== CUSTOM FIELDS ==========

    async def update_custom_field(
        self,
        contact_id: str,
        field_key: str,
        field_value: Any
    ) -> bool:
        """
        Update custom field value for contact.

        Jorge's Custom Fields:
        - ai_lead_score: 0-100
        - lead_temperature: hot/warm/cold
        - budget_min: number
        - budget_max: number
        - timeline: string
        - financing_status: string

        Returns:
            True if successful, False otherwise
        """
        result = await self.update_contact(contact_id, {
            "customField": {field_key: field_value}
        })
        return result.get("success", False)

    # ========== OPPORTUNITIES ==========

    async def create_opportunity(self, opportunity_data: Dict) -> Dict:
        """Create new opportunity."""
        opportunity_data["locationId"] = self.location_id
        return await self._make_request("POST", "opportunities", data=opportunity_data)

    async def update_opportunity(self, opportunity_id: str, updates: Dict) -> Dict:
        """Update opportunity."""
        return await self._make_request("PUT", f"opportunities/{opportunity_id}", data=updates)

    async def get_opportunity(self, opportunity_id: str) -> Dict:
        """Get opportunity by ID."""
        return await self._make_request("GET", f"opportunities/{opportunity_id}")

    async def delete_opportunity(self, opportunity_id: str) -> Dict:
        """Delete opportunity."""
        return await self._make_request("DELETE", f"opportunities/{opportunity_id}")

    # ========== MESSAGING & CONVERSATIONS ==========

    async def send_message(
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
        return await self._make_request("POST", "conversations/messages", data=data)

    async def get_conversations(self, contact_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history for contact.

        Args:
            contact_id: GHL Contact ID

        Returns:
            List of conversations
        """
        result = await self._make_request(
            "GET",
            "conversations",
            params={"contactId": contact_id}
        )
        if result.get("success"):
            return result.get("data", {}).get("conversations", [])
        return []

    # ========== WORKFLOWS & AUTOMATION ==========

    async def trigger_workflow(self, contact_id: str, workflow_id: str) -> Dict:
        """
        Trigger workflow for contact.

        Args:
            contact_id: GHL Contact ID
            workflow_id: Workflow ID to trigger

        Returns:
            Workflow trigger result
        """
        data = {
            "contactId": contact_id,
            "workflowId": workflow_id
        }
        return await self._make_request(
            "POST",
            f"workflows/{workflow_id}/subscribe",
            data=data
        )

    # ========== CALENDAR & APPOINTMENTS ==========

    async def create_appointment(self, appointment_data: Dict[str, Any]) -> Dict:
        """
        Create calendar appointment in GHL.

        Args:
            appointment_data: Appointment details (contactId, calendarId, startTime, etc.)

        Returns:
            Created appointment data
        """
        return await self._make_request("POST", "calendars/events", data=appointment_data)

    async def get_appointment(self, appointment_id: str) -> Dict:
        """Get appointment by ID."""
        return await self._make_request("GET", f"calendars/events/{appointment_id}")

    async def update_appointment(self, appointment_id: str, updates: Dict) -> Dict:
        """Update appointment."""
        return await self._make_request("PUT", f"calendars/events/{appointment_id}", data=updates)

    async def delete_appointment(self, appointment_id: str) -> Dict:
        """Delete appointment."""
        return await self._make_request("DELETE", f"calendars/events/{appointment_id}")

    # ========== BATCH OPERATIONS ==========

    async def apply_actions(self, contact_id: str, actions: List[Dict[str, Any]]) -> bool:
        """
        Apply multiple actions to a contact.

        Supported action types:
        - add_tag: {"type": "add_tag", "tag": "Hot Lead"}
        - remove_tag: {"type": "remove_tag", "tag": "Cold Lead"}
        - update_custom_field: {"type": "update_custom_field", "field": "ai_lead_score", "value": "95"}
        - trigger_workflow: {"type": "trigger_workflow", "workflow_id": "workflow_123"}
        - send_message: {"type": "send_message", "message": "Hello!"}

        Args:
            contact_id: GHL Contact ID
            actions: List of action dictionaries

        Returns:
            True if all actions succeeded, False if any failed
        """
        success = True

        for action in actions:
            try:
                action_type = action.get("type")

                if action_type == "add_tag":
                    result = await self.add_tag(contact_id, action["tag"])
                elif action_type == "remove_tag":
                    result = await self.remove_tag(contact_id, action["tag"])
                elif action_type == "update_custom_field":
                    result = await self.update_custom_field(
                        contact_id, action["field"], action["value"]
                    )
                elif action_type == "trigger_workflow":
                    result_dict = await self.trigger_workflow(
                        contact_id, action["workflow_id"]
                    )
                    result = result_dict.get("success", False)
                elif action_type == "send_message":
                    result_dict = await self.send_message(
                        contact_id, action["message"]
                    )
                    result = result_dict.get("success", False)
                else:
                    logger.warning(f"Unknown action type: {action_type}")
                    result = False

                if not result:
                    success = False

            except Exception as e:
                logger.error(f"Error applying action {action}: {e}")
                success = False

        return success

    # ========== JORGE-SPECIFIC METHODS ==========

    async def update_lead_score(
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
        return await self.update_contact(contact_id, {
            "customField": {
                "ai_lead_score": score,
                "lead_temperature": temperature
            }
        })

    async def update_budget_and_timeline(
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

        return await self.update_contact(contact_id, {
            "customField": custom_fields
        })

    async def send_immediate_followup(
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
        return await self.send_message(
            contact_id=contact_id,
            message=message,
            message_type="SMS"
        )

    # ========== HEALTH & MONITORING ==========

    async def health_check(self) -> Dict:
        """
        Check API connection health.

        Returns:
            Health status
        """
        try:
            result = await self._make_request(
                "GET",
                "contacts",
                params={"limit": 1, "locationId": self.location_id}
            )
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

    def check_health_sync(self) -> Dict:
        """
        Synchronous health check (for non-async contexts).

        Returns:
            Health status
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    f"{self.BASE_URL}/contacts",
                    headers=self.headers,
                    params={"limit": 1, "locationId": self.location_id}
                )
                return {
                    "healthy": response.status_code == 200,
                    "api_key_valid": response.status_code == 200,
                    "location_id": self.location_id,
                    "status_code": response.status_code,
                    "checked_at": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }

    async def close(self):
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Factory functions
def get_ghl_client() -> GHLClient:
    """Get a GHL client instance."""
    return GHLClient()


def create_ghl_client(api_key: Optional[str] = None) -> GHLClient:
    """
    Create and configure GHL client.

    Args:
        api_key: Optional GHL API key (defaults to settings)

    Returns:
        Configured GHLClient instance
    """
    return GHLClient(api_key=api_key)
