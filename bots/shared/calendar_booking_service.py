"""
Calendar booking service for Jorge's HOT seller/buyer appointments.

Integrates with GHL Calendar API to offer and book appointment slots
when a lead is classified as HOT. Provides graceful fallback when the
calendar is not configured or unavailable.
"""
import re
from datetime import datetime
from typing import Dict, List, Optional

from bots.shared.config import settings
from bots.shared.logger import get_logger

logger = get_logger(__name__)

# Shown when JORGE_CALENDAR_ID is unset or no slots are available
FALLBACK_MESSAGE = (
    "I'd love to schedule a time to discuss your options in detail. "
    "What would work better for you, morning or afternoon?"
)


class CalendarBookingService:
    """Offer and book GHL calendar appointments for HOT leads via SMS."""

    def __init__(self, ghl_client):
        """
        Args:
            ghl_client: A GHLClient instance (used for get_free_slots / create_appointment).
        """
        self.ghl_client = ghl_client
        self.calendar_id: str = settings.jorge_calendar_id or ""
        self.user_id: str = settings.jorge_user_id or ""
        # In-process slot cache: {contact_id: [slot_dict, ...]}
        # Cleared on server restart — handled gracefully in book_appointment.
        self._pending_slots: Dict[str, List[Dict]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def offer_appointment_slots(
        self, contact_id: str, lead_type: str = "seller"
    ) -> Dict:
        """
        Fetch available slots and return a formatted SMS offering 1–3 options.

        Args:
            contact_id: GHL contact ID for the lead.
            lead_type: "seller" or "buyer" (used for appointment title on booking).

        Returns:
            Dict with:
              - message: str  — SMS text to send
              - slots: list   — raw slot data (empty if fallback)
              - fallback: bool — True if calendar unavailable
        """
        if not self.calendar_id:
            logger.warning("JORGE_CALENDAR_ID not configured — using fallback message")
            return {"message": FALLBACK_MESSAGE, "slots": [], "fallback": True}

        try:
            slots = await self.ghl_client.get_free_slots(self.calendar_id)
        except Exception as exc:
            logger.error(f"get_free_slots error for {contact_id}: {exc}")
            return {"message": FALLBACK_MESSAGE, "slots": [], "fallback": True}

        if not slots:
            logger.info(f"No available slots for contact {contact_id}")
            return {"message": FALLBACK_MESSAGE, "slots": [], "fallback": True}

        self._pending_slots[contact_id] = slots
        return {
            "message": self._format_slot_options(slots),
            "slots": slots,
            "fallback": False,
        }

    async def book_appointment(
        self, contact_id: str, slot_index: int, lead_type: str = "seller"
    ) -> Dict:
        """
        Book the selected slot for a contact.

        Args:
            contact_id: GHL contact ID.
            slot_index: 0-based index of the chosen slot.
            lead_type: "seller" or "buyer" (sets appointment title).

        Returns:
            Dict with:
              - success: bool
              - appointment: dict or None
              - message: str — confirmation or error SMS text
        """
        slots = self._pending_slots.get(contact_id)
        if not slots:
            return {
                "success": False,
                "appointment": None,
                "message": (
                    "No pending slots found. Let me get fresh availability for you."
                ),
            }

        if slot_index < 0 or slot_index >= len(slots):
            return {
                "success": False,
                "appointment": None,
                "message": f"Please choose a valid option (1–{len(slots)}).",
            }

        slot = slots[slot_index]
        title = "Seller Consultation" if lead_type == "seller" else "Buyer Consultation"
        appointment_data: Dict = {
            "calendarId": self.calendar_id,
            "locationId": self.ghl_client.location_id,
            "contactId": contact_id,
            "startTime": slot["start"],
            "endTime": slot["end"],
            "title": title,
            "appointmentStatus": "new",
        }
        if self.user_id:
            appointment_data["assignedUserId"] = self.user_id

        try:
            result = await self.ghl_client.create_appointment(appointment_data)
        except Exception as exc:
            logger.error(f"create_appointment error for {contact_id}: {exc}")
            return {
                "success": False,
                "appointment": None,
                "message": "I wasn't able to book that slot. Let me find other times for you.",
            }

        if result.get("success"):
            self._pending_slots.pop(contact_id, None)
            appointment = result.get("data", {})
            return {
                "success": True,
                "appointment": appointment,
                "message": self._format_confirmation(slot),
            }

        return {
            "success": False,
            "appointment": None,
            "message": "I wasn't able to book that slot. Let me find other times for you.",
        }

    def has_pending_slots(self, contact_id: str) -> bool:
        """Return True if there are cached slots for this contact."""
        return bool(self._pending_slots.get(contact_id))

    @staticmethod
    def detect_slot_selection(message: str) -> Optional[int]:
        """
        Parse a slot-selection reply from the lead.

        Accepts bare digits ("1"), prefixed forms ("slot 2", "#3", "option 1"),
        and returns a 0-based index. Returns None if no slot number found.

        Args:
            message: Raw SMS text from the lead.

        Returns:
            0-based slot index (0, 1, or 2) or None.
        """
        msg = message.strip()
        patterns = [
            r"^\s*([123])\s*$",                    # bare single digit
            r"(?:slot|option|#)\s*([123])\b",      # "slot 2", "#3", "option 1"
        ]
        for pattern in patterns:
            match = re.search(pattern, msg, re.IGNORECASE)
            if match:
                return int(match.group(1)) - 1
        return None

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _format_slot_options(self, slots: List[Dict]) -> str:
        """Format a list of slots into a numbered SMS message."""
        lines = ["Here are some times I have available:\n"]
        for i, slot in enumerate(slots, 1):
            lines.append(f"  {i}. {self._format_slot_time(slot)}")
        lines.append("\nJust reply with the number that works best!")
        return "\n".join(lines)

    def _format_confirmation(self, slot: Dict) -> str:
        """Format a booking confirmation message."""
        formatted = self._format_slot_time(slot)
        return (
            f"You're all set! Your consultation is booked for {formatted}. "
            "Looking forward to it!"
        )

    @staticmethod
    def _format_slot_time(slot: Dict) -> str:
        """Format a single slot's start time for display (e.g. 'Friday, March 1 at 10:00 AM')."""
        start = slot.get("start", "")
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            return dt.strftime("%A, %B %d at %I:%M %p")
        except (ValueError, AttributeError):
            return start
