"""
Pydantic Models for Lead Bot API.

Request/response validation models for FastAPI endpoints.
Extracted from: jorge_deployment_package/jorge_fastapi_lead_bot.py
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any


class LeadMessage(BaseModel):
    """Lead message input model for direct analysis."""
    contact_id: str = Field(..., description="GHL contact ID")
    location_id: str = Field(..., description="GHL location ID")
    message: str = Field(..., description="Lead's message content")
    contact_data: Optional[Dict[str, Any]] = Field(None, description="Additional contact information")
    force_ai_analysis: bool = Field(False, description="Force Claude AI analysis even if cached")


class GHLWebhook(BaseModel):
    """GoHighLevel webhook payload model."""
    type: str = Field(..., description="Webhook event type")
    location_id: str = Field(..., description="GHL location ID")
    contact_id: str = Field(..., description="Contact ID")
    message: Optional[str] = Field(None, description="Message content")
    contact: Optional[Dict[str, Any]] = Field(None, description="Contact data")
    conversation: Optional[Dict[str, Any]] = Field(None, description="Conversation data")
    timestamp: Optional[str] = Field(None, description="Event timestamp")


class LeadAnalysisResponse(BaseModel):
    """Lead analysis response model."""
    success: bool = Field(..., description="Analysis success status")
    lead_score: float = Field(..., description="Lead score (0-100)")
    lead_temperature: str = Field(..., description="Lead temperature (Hot/Warm/Cold)")
    jorge_priority: str = Field(..., description="Priority for Jorge (high/normal/review)")
    estimated_commission: float = Field(default=0.0, description="Estimated commission ($)")
    meets_jorge_criteria: bool = Field(..., description="Passes Jorge's business rules")
    performance: Dict[str, Any] = Field(..., description="Performance metrics")
    jorge_validation: Optional[Dict[str, Any]] = Field(None, description="Jorge's business rules validation")


class PerformanceStatus(BaseModel):
    """Performance monitoring status model."""
    five_minute_rule_compliant: bool = Field(..., description="5-minute rule compliance status")
    total_requests: int = Field(..., description="Total requests processed")
    avg_response_time_ms: float = Field(..., description="Average response time (ms)")
    cache_hit_rate: float = Field(..., description="Cache hit rate (%)")
