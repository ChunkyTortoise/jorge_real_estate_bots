"""
Shared data models for Jorge's Real Estate Bots.

Contains dataclasses and Pydantic models used across the system.
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class PerformanceMetrics:
    """
    Track performance metrics for 5-minute rule compliance.

    Used to monitor lead analysis performance and ensure
    responses stay under the critical 5-minute threshold.

    Extracted from: jorge_deployment_package/jorge_claude_intelligence.py
    """
    start_time: float
    pattern_analysis_time: Optional[float] = None
    claude_analysis_time: Optional[float] = None
    total_time: Optional[float] = None
    cache_hit: bool = False
    analysis_type: str = "unknown"  # "cached", "pattern", "hybrid", "fallback"
    five_minute_rule_compliant: bool = True

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "start_time": self.start_time,
            "pattern_analysis_time": self.pattern_analysis_time,
            "claude_analysis_time": self.claude_analysis_time,
            "total_time": self.total_time,
            "cache_hit": self.cache_hit,
            "analysis_type": self.analysis_type,
            "five_minute_rule_compliant": self.five_minute_rule_compliant
        }
