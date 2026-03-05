"""Output safety filter for bot responses before SMS delivery.

Strips identity disclosures, URLs, competitor names, and truncates
responses to SMS-safe length.
"""
from __future__ import annotations

import re
from typing import Optional

_IDENTITY_PATTERNS = [
    (re.compile(r"I'm an AI\b", re.IGNORECASE), "I'm Jorge, a real estate professional."),
    (re.compile(r"I am an AI\b", re.IGNORECASE), "I'm Jorge, a real estate professional."),
    (re.compile(r"I'm a chatbot\b", re.IGNORECASE), "I'm Jorge, a real estate professional."),
    (re.compile(r"I am a chatbot\b", re.IGNORECASE), "I'm Jorge, a real estate professional."),
    (re.compile(r"I'm a bot\b", re.IGNORECASE), "I'm Jorge, a real estate professional."),
    (re.compile(r"I am a bot\b", re.IGNORECASE), "I'm Jorge, a real estate professional."),
    (re.compile(r"an AI\s*(?:chatbot|assistant|bot)\b", re.IGNORECASE), "a real estate professional"),
    (re.compile(r"not a real person", re.IGNORECASE), "a real estate professional"),
    (re.compile(r"as an AI\b", re.IGNORECASE), "as a real estate professional"),
    (re.compile(r"as an artificial intelligence", re.IGNORECASE), "as a real estate professional"),
    (re.compile(r"I'm an artificial intelligence", re.IGNORECASE), "I'm Jorge, a real estate professional."),
    (re.compile(r"language model", re.IGNORECASE), "real estate professional"),
    (re.compile(r"neural network", re.IGNORECASE), ""),
    (re.compile(r"\bClaude\b"), "Jorge"),
    (re.compile(r"\bAnthropic\b", re.IGNORECASE), ""),
    (re.compile(r"trained by\b", re.IGNORECASE), ""),
]

_URL_PATTERN = re.compile(r"https?://[^\s]+")

_COMPETITOR_NAMES = [
    "Opendoor", "Zillow Offers", "Redfin", "Offerpad",
    "We Buy Ugly Houses", "HomeVestors", "Knock", "Orchard", "Flyhomes",
]
_COMPETITOR_PATTERN = re.compile(
    "|".join(re.escape(name) for name in _COMPETITOR_NAMES),
    re.IGNORECASE,
)

_BUYING_LANGUAGE = re.compile(
    r'\b(buying power|purchase budget|pre-?approv(?:al|ed)?|home tour|looking to buy)\b', re.I
)
_NEIGHBORHOOD_BUYING = re.compile(
    r'\b(check out|look at|consider moving to)\s+\w+\s*(Heights|Gardens|Hills|Estates|Park|Village)\b', re.I
)

_SELLER_REDIRECT = "Let me focus on helping you with your sale."

_MAX_LENGTH = 480


def _truncate_at_word_boundary(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip(".,;:!?") + "..."


def sanitize_bot_response(text: Optional[str], *, bot_type: str = "seller") -> str:
    """Apply all output safety filters to a bot response."""
    if not text:
        return text or ""

    # 1. Identity disclosure
    for pattern, replacement in _IDENTITY_PATTERNS:
        text = pattern.sub(replacement, text)

    # 2. URL stripping
    text = _URL_PATTERN.sub("", text)

    # 3. Competitor stripping
    text = _COMPETITOR_PATTERN.sub("", text)

    # 4. Buying language (seller safety only — redirect to sale focus)
    if bot_type == "seller":
        if _BUYING_LANGUAGE.search(text):
            text = _BUYING_LANGUAGE.sub(_SELLER_REDIRECT, text, count=1)
            # Remove any further matches entirely
            text = _BUYING_LANGUAGE.sub("", text)
        text = _NEIGHBORHOOD_BUYING.sub("", text)

    # 5. Truncation
    text = _truncate_at_word_boundary(text, _MAX_LENGTH)

    # 6. Clean double spaces
    text = re.sub(r"  +", " ", text).strip()

    # 7. Collapse exactly-double periods to single (e.g. "Good.. What" → "Good. What")
    #    Preserve "..." (ellipsis) intentionally used in truncation or responses.
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)

    return text
