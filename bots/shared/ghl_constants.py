"""Centralized GHL string constants and field ID map."""

JORGE_TAG_PREFIX = "jorge-"
JORGE_ACTIVE_TAG = "Jorge-Active"
JORGE_QUALIFIED_PREFIX = "jorge-qualified-"
JORGE_TEMP_PREFIX = "jorge-temp-"
API_VERSION = "2021-07-28"

# GHL custom field ID map — maps internal logical names to GHL field IDs.
# Field IDs sourced from .env.jorge (obtained via GHL API).
GHL_FIELD_MAP: dict[str, str] = {
    "seller_temperature": "jkQFooyVp0OEcaYVNJQL",
    "seller_motivation": "70kCdEvjjia40FXwJCvZ",
    "timeline_urgency": "eiJZQF91jI0dAv5TudPv",
    "property_condition": "HEsrvb0eSYHR9kIPVzVx",
    "price_expectation": "TH5M68o73lTdJmvaodjN",
    "questions_answered": "JWMo3frSjaUd2cs60trd",
    "qualification_score": "vRKYsiyXLnFXUsQtqBLo",
    "property_address": "AoCxlGK7K1MMiWrs6ZvF",
    "qualification_complete": "bOfcrncwqL7L9ABwIVLM",
    "pcs_score": "ZJmEZ7yfLYoGKxobUxEB",
    "seller_liens": "otCGQZCPIrQQeNSReNOL",
    "seller_repairs": "0PMZEMBmgEm0OYVIly1z",
    "seller_listing_history": "KtuK8hUm4fKtEPg6Nt8P",
    "seller_decision_maker": "gSLknRJ2I2wdPLZcr8fG",
    "buyer_temperature": "r1k8LHLKrIVqhy94glX2",
    "pre_approval_status": "9W0ar8g6cgih26aMY7cy",
    "property_preferences": "kJLLkopXwBigKn0PWvGI",
    "budget": "2XyZHYEFD6YjXkv6D2xN",
    "lead_score": "barDqSiziV2XsVw6WKKb",
    "location": "XdIrAUGWXHTZnFWKSOMY",
    "timeline": "SJc5eQHa1wraqKvEn3GF",
    "frs": "H6ogTJCOSJYkT1UaNUZ4",
    "buyer_intent": "X40wlBi8kJE7JKo4cTY3",
    "seller_intent": "mqkuWxpQNjPCE1BCoTdN",
    "temperature": "jkQFooyVp0OEcaYVNJQL",
    "handoff_history": "2FpBMFbI74uk8OZrCAjx",
    "last_bot": "0jGS8XMHWbHTXQmYTNZb",
    "conversation_context": "fAh7vhfxWaOECV47sQ77",
    "appointment_time": "YOz5TyIJULJm4aTKbJZu",
    "appointment_type": "JqEiYvsEs1EW4CYOKF6s",
}
