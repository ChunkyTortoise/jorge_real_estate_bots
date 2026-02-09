"""
Event Models for Jorge Real Estate AI Real-Time Dashboard

This module defines Pydantic models for all event types in the Jorge system:
- Lead events (10 types): Analysis, scoring, caching, GHL updates
- GHL events (6 types): Contact updates, tags, workflows, API operations
- Cache events (3 types): Hit, miss, set operations
- System events (2 types): Performance, health monitoring

Events follow a standard schema with validation, serialization, and type safety.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventCategory(str, Enum):
    """Event category types for channel routing"""
    LEADS = "leads"
    GHL = "ghl"
    CACHE = "cache"
    SYSTEM = "system"


class LeadTemperature(str, Enum):
    """Lead temperature classifications"""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class JorgePriority(str, Enum):
    """Jorge priority levels"""
    HIGH = "high"
    NORMAL = "normal"
    REVIEW = "review"


class BaseEvent(BaseModel):
    """
    Base event model with common fields for all event types.

    All events include:
    - Unique event ID for deduplication
    - ISO timestamp for ordering
    - Event type for routing and filtering
    - Source service identification
    - Structured payload data
    """
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str
    source: str
    payload: Dict[str, Any]

    model_config = ConfigDict()

    @property
    def category(self) -> EventCategory:
        """Extract event category from event type"""
        if self.event_type.startswith("lead."):
            return EventCategory.LEADS
        elif self.event_type.startswith("ghl."):
            return EventCategory.GHL
        elif self.event_type.startswith("cache."):
            return EventCategory.CACHE
        elif self.event_type.startswith("system."):
            return EventCategory.SYSTEM
        else:
            return EventCategory.SYSTEM

    def sanitize_payload(self) -> Dict[str, Any]:
        """Remove sensitive information from payload for client transmission"""
        sensitive_fields = ['email', 'phone', 'ssn', 'api_key', 'token']
        return {
            k: v for k, v in self.payload.items()
            if k not in sensitive_fields
        }


# =============================================================================
# LEAD EVENTS (10 types)
# =============================================================================

class LeadAnalyzedEvent(BaseEvent):
    """Lead analysis completed with AI scoring"""
    event_type: Literal["lead.analyzed"] = "lead.analyzed"
    source: Literal["lead_analyzer"] = "lead_analyzer"

    # Typed payload fields
    contact_id: str
    score: int = Field(..., ge=0, le=100)
    temperature: LeadTemperature
    jorge_priority: JorgePriority
    estimated_commission: float = Field(..., ge=0)
    meets_jorge_criteria: bool
    analysis_time_ms: float
    cache_hit: bool

    def __init__(self, **data):
        # Move typed fields to payload
        payload = {
            "contact_id": data.pop("contact_id"),
            "score": data.pop("score"),
            "temperature": data.pop("temperature"),
            "jorge_priority": data.pop("jorge_priority"),
            "estimated_commission": data.pop("estimated_commission"),
            "meets_jorge_criteria": data.pop("meets_jorge_criteria"),
            "analysis_time_ms": data.pop("analysis_time_ms"),
            "cache_hit": data.pop("cache_hit")
        }
        super().__init__(payload=payload, **data)


class LeadScoredEvent(BaseEvent):
    """Lead score calculated"""
    event_type: Literal["lead.scored"] = "lead.scored"
    source: Literal["lead_analyzer"] = "lead_analyzer"

    contact_id: str
    score: int = Field(..., ge=0, le=100)
    previous_score: Optional[int] = None
    score_change: Optional[int] = None

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "score": data.pop("score"),
            "previous_score": data.pop("previous_score", None),
            "score_change": data.pop("score_change", None)
        }
        super().__init__(payload=payload, **data)


class LeadCacheHitEvent(BaseEvent):
    """Lead data retrieved from cache"""
    event_type: Literal["lead.cache_hit"] = "lead.cache_hit"
    source: Literal["lead_analyzer"] = "lead_analyzer"

    contact_id: str
    cache_key: str
    response_time_ms: float

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "cache_key": data.pop("cache_key"),
            "response_time_ms": data.pop("response_time_ms")
        }
        super().__init__(payload=payload, **data)


class LeadCacheMissEvent(BaseEvent):
    """Lead data not found in cache, computing fresh"""
    event_type: Literal["lead.cache_miss"] = "lead.cache_miss"
    source: Literal["lead_analyzer"] = "lead_analyzer"

    contact_id: str
    cache_key: str

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "cache_key": data.pop("cache_key")
        }
        super().__init__(payload=payload, **data)


class LeadGHLUpdatedEvent(BaseEvent):
    """GHL fields updated for lead"""
    event_type: Literal["lead.ghl_updated"] = "lead.ghl_updated"
    source: Literal["lead_analyzer"] = "lead_analyzer"

    contact_id: str
    fields_updated: list[str]
    update_success: bool
    error_message: Optional[str] = None

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "fields_updated": data.pop("fields_updated"),
            "update_success": data.pop("update_success"),
            "error_message": data.pop("error_message", None)
        }
        super().__init__(payload=payload, **data)


class LeadFollowupSentEvent(BaseEvent):
    """Follow-up message sent to lead"""
    event_type: Literal["lead.followup_sent"] = "lead.followup_sent"
    source: Literal["lead_analyzer"] = "lead_analyzer"

    contact_id: str
    temperature: LeadTemperature
    message_type: Literal["sms", "email"]
    message_sent: bool

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "temperature": data.pop("temperature"),
            "message_type": data.pop("message_type"),
            "message_sent": data.pop("message_sent")
        }
        super().__init__(payload=payload, **data)


class LeadJorgeValidatedEvent(BaseEvent):
    """Lead meets Jorge criteria validation"""
    event_type: Literal["lead.jorge_validated"] = "lead.jorge_validated"
    source: Literal["lead_analyzer"] = "lead_analyzer"

    contact_id: str
    meets_criteria: bool
    criteria_met: list[str]
    criteria_failed: list[str]

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "meets_criteria": data.pop("meets_criteria"),
            "criteria_met": data.pop("criteria_met"),
            "criteria_failed": data.pop("criteria_failed")
        }
        super().__init__(payload=payload, **data)


class LeadHotDetectedEvent(BaseEvent):
    """Hot lead detected (temperature = hot)"""
    event_type: Literal["lead.hot_detected"] = "lead.hot_detected"
    source: Literal["lead_analyzer"] = "lead_analyzer"

    contact_id: str
    score: int
    estimated_commission: float
    hot_indicators: list[str]

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "score": data.pop("score"),
            "estimated_commission": data.pop("estimated_commission"),
            "hot_indicators": data.pop("hot_indicators")
        }
        super().__init__(payload=payload, **data)


class LeadErrorEvent(BaseEvent):
    """Error occurred during lead processing"""
    event_type: Literal["lead.error"] = "lead.error"
    source: Literal["lead_analyzer"] = "lead_analyzer"

    contact_id: str
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "error_type": data.pop("error_type"),
            "error_message": data.pop("error_message"),
            "stack_trace": data.pop("stack_trace", None)
        }
        super().__init__(payload=payload, **data)


class LeadFallbackUsedEvent(BaseEvent):
    """Fallback logic used for lead analysis"""
    event_type: Literal["lead.fallback_used"] = "lead.fallback_used"
    source: Literal["lead_analyzer"] = "lead_analyzer"

    contact_id: str
    fallback_reason: str
    fallback_type: str

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "fallback_reason": data.pop("fallback_reason"),
            "fallback_type": data.pop("fallback_type")
        }
        super().__init__(payload=payload, **data)


# =============================================================================
# GHL EVENTS (6 types)
# =============================================================================

class GHLContactUpdatedEvent(BaseEvent):
    """GHL contact information updated"""
    event_type: Literal["ghl.contact_updated"] = "ghl.contact_updated"
    source: Literal["ghl_client"] = "ghl_client"

    contact_id: str
    fields_updated: Dict[str, Any]
    update_success: bool

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "fields_updated": data.pop("fields_updated"),
            "update_success": data.pop("update_success")
        }
        super().__init__(payload=payload, **data)


class GHLTagAddedEvent(BaseEvent):
    """Tag added to GHL contact"""
    event_type: Literal["ghl.tag_added"] = "ghl.tag_added"
    source: Literal["ghl_client"] = "ghl_client"

    contact_id: str
    tag: str
    tag_added: bool

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "tag": data.pop("tag"),
            "tag_added": data.pop("tag_added")
        }
        super().__init__(payload=payload, **data)


class GHLOpportunityCreatedEvent(BaseEvent):
    """Opportunity created in GHL"""
    event_type: Literal["ghl.opportunity_created"] = "ghl.opportunity_created"
    source: Literal["ghl_client"] = "ghl_client"

    contact_id: str
    opportunity_id: str
    estimated_value: float
    stage: str

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "opportunity_id": data.pop("opportunity_id"),
            "estimated_value": data.pop("estimated_value"),
            "stage": data.pop("stage")
        }
        super().__init__(payload=payload, **data)


class GHLMessageSentEvent(BaseEvent):
    """Message sent via GHL"""
    event_type: Literal["ghl.message_sent"] = "ghl.message_sent"
    source: Literal["ghl_client"] = "ghl_client"

    contact_id: str
    message_type: Literal["sms", "email"]
    message_id: str
    sent_success: bool

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "message_type": data.pop("message_type"),
            "message_id": data.pop("message_id"),
            "sent_success": data.pop("sent_success")
        }
        super().__init__(payload=payload, **data)


class GHLWorkflowTriggeredEvent(BaseEvent):
    """Workflow triggered in GHL"""
    event_type: Literal["ghl.workflow_triggered"] = "ghl.workflow_triggered"
    source: Literal["ghl_client"] = "ghl_client"

    contact_id: str
    workflow_id: str
    workflow_name: str
    trigger_success: bool

    def __init__(self, **data):
        payload = {
            "contact_id": data.pop("contact_id"),
            "workflow_id": data.pop("workflow_id"),
            "workflow_name": data.pop("workflow_name"),
            "trigger_success": data.pop("trigger_success")
        }
        super().__init__(payload=payload, **data)


class GHLAPIErrorEvent(BaseEvent):
    """Error in GHL API operation"""
    event_type: Literal["ghl.api_error"] = "ghl.api_error"
    source: Literal["ghl_client"] = "ghl_client"

    operation: str
    error_code: int
    error_message: str
    contact_id: Optional[str] = None

    def __init__(self, **data):
        payload = {
            "operation": data.pop("operation"),
            "error_code": data.pop("error_code"),
            "error_message": data.pop("error_message"),
            "contact_id": data.pop("contact_id", None)
        }
        super().__init__(payload=payload, **data)


# =============================================================================
# CACHE EVENTS (3 types)
# =============================================================================

class CacheHitEvent(BaseEvent):
    """Cache hit occurred"""
    event_type: Literal["cache.hit"] = "cache.hit"
    source: Literal["cache_service"] = "cache_service"

    cache_key: str
    response_time_ms: float
    data_size_bytes: Optional[int] = None

    def __init__(self, **data):
        payload = {
            "cache_key": data.pop("cache_key"),
            "response_time_ms": data.pop("response_time_ms"),
            "data_size_bytes": data.pop("data_size_bytes", None)
        }
        super().__init__(payload=payload, **data)


class CacheMissEvent(BaseEvent):
    """Cache miss occurred"""
    event_type: Literal["cache.miss"] = "cache.miss"
    source: Literal["cache_service"] = "cache_service"

    cache_key: str

    def __init__(self, **data):
        payload = {
            "cache_key": data.pop("cache_key")
        }
        super().__init__(payload=payload, **data)


class CacheSetEvent(BaseEvent):
    """Data set in cache"""
    event_type: Literal["cache.set"] = "cache.set"
    source: Literal["cache_service"] = "cache_service"

    cache_key: str
    ttl_seconds: int
    data_size_bytes: int

    def __init__(self, **data):
        payload = {
            "cache_key": data.pop("cache_key"),
            "ttl_seconds": data.pop("ttl_seconds"),
            "data_size_bytes": data.pop("data_size_bytes")
        }
        super().__init__(payload=payload, **data)


# =============================================================================
# SYSTEM EVENTS (2 types)
# =============================================================================

class SystemPerformanceEvent(BaseEvent):
    """System performance metrics"""
    event_type: Literal["system.performance"] = "system.performance"
    source: Literal["system"] = "system"

    avg_response_time_ms: float
    cache_hit_rate: float = Field(..., ge=0, le=1)
    five_minute_compliance: bool
    active_connections: int
    events_per_second: float

    def __init__(self, **data):
        payload = {
            "avg_response_time_ms": data.pop("avg_response_time_ms"),
            "cache_hit_rate": data.pop("cache_hit_rate"),
            "five_minute_compliance": data.pop("five_minute_compliance"),
            "active_connections": data.pop("active_connections"),
            "events_per_second": data.pop("events_per_second")
        }
        super().__init__(payload=payload, **data)


class SystemHealthEvent(BaseEvent):
    """System health check"""
    event_type: Literal["system.health"] = "system.health"
    source: Literal["system"] = "system"

    redis_healthy: bool
    ghl_api_healthy: bool
    lead_analyzer_healthy: bool
    websocket_healthy: bool
    overall_health: Literal["healthy", "degraded", "unhealthy"]

    def __init__(self, **data):
        payload = {
            "redis_healthy": data.pop("redis_healthy"),
            "ghl_api_healthy": data.pop("ghl_api_healthy"),
            "lead_analyzer_healthy": data.pop("lead_analyzer_healthy"),
            "websocket_healthy": data.pop("websocket_healthy"),
            "overall_health": data.pop("overall_health")
        }
        super().__init__(payload=payload, **data)


# =============================================================================
# EVENT TYPE UNION
# =============================================================================

EventType = Union[
    # Lead events
    LeadAnalyzedEvent,
    LeadScoredEvent,
    LeadCacheHitEvent,
    LeadCacheMissEvent,
    LeadGHLUpdatedEvent,
    LeadFollowupSentEvent,
    LeadJorgeValidatedEvent,
    LeadHotDetectedEvent,
    LeadErrorEvent,
    LeadFallbackUsedEvent,

    # GHL events
    GHLContactUpdatedEvent,
    GHLTagAddedEvent,
    GHLOpportunityCreatedEvent,
    GHLMessageSentEvent,
    GHLWorkflowTriggeredEvent,
    GHLAPIErrorEvent,

    # Cache events
    CacheHitEvent,
    CacheMissEvent,
    CacheSetEvent,

    # System events
    SystemPerformanceEvent,
    SystemHealthEvent
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_event(event_type: str, **kwargs) -> EventType:
    """Factory function to create events by type string"""
    event_map = {
        "lead.analyzed": LeadAnalyzedEvent,
        "lead.scored": LeadScoredEvent,
        "lead.cache_hit": LeadCacheHitEvent,
        "lead.cache_miss": LeadCacheMissEvent,
        "lead.ghl_updated": LeadGHLUpdatedEvent,
        "lead.followup_sent": LeadFollowupSentEvent,
        "lead.jorge_validated": LeadJorgeValidatedEvent,
        "lead.hot_detected": LeadHotDetectedEvent,
        "lead.error": LeadErrorEvent,
        "lead.fallback_used": LeadFallbackUsedEvent,

        "ghl.contact_updated": GHLContactUpdatedEvent,
        "ghl.tag_added": GHLTagAddedEvent,
        "ghl.opportunity_created": GHLOpportunityCreatedEvent,
        "ghl.message_sent": GHLMessageSentEvent,
        "ghl.workflow_triggered": GHLWorkflowTriggeredEvent,
        "ghl.api_error": GHLAPIErrorEvent,

        "cache.hit": CacheHitEvent,
        "cache.miss": CacheMissEvent,
        "cache.set": CacheSetEvent,

        "system.performance": SystemPerformanceEvent,
        "system.health": SystemHealthEvent,
    }

    if event_type not in event_map:
        raise ValueError(f"Unknown event type: {event_type}")

    return event_map[event_type](**kwargs)


def get_event_channel(event: BaseEvent) -> str:
    """Get Redis channel name for event"""
    return f"jorge:events:{event.category.value}"


def get_event_stream(event: BaseEvent) -> str:
    """Get Redis stream name for event persistence"""
    return f"jorge:stream:{event.category.value}"