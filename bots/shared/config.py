"""
Configuration module for Jorge's Real Estate AI Bots.

Manages environment variables and application settings using Pydantic.
Adapted from EnterpriseHub for Jorge's specific requirements.
"""
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application settings with environment variable support.

    All sensitive values (API keys, database URLs) are loaded from environment
    variables or .env file. Never hardcode secrets in this file.
    """

    # ========== CRITICAL API KEYS ==========
    anthropic_api_key: str
    ghl_api_key: str
    ghl_location_id: str
    zillow_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    sendgrid_api_key: str = ""

    # ========== CLAUDE AI CONFIGURATION ==========
    claude_model: str = "claude-3-5-sonnet-20241022"
    claude_sonnet_model: str = "claude-3-5-sonnet-20241022"
    claude_haiku_model: str = "claude-3-5-haiku-20241022"
    claude_opus_model: str = "claude-3-opus-20240229"

    # Default LLM Provider
    default_llm_provider: str = "claude"

    # LLM Generation Parameters
    temperature: float = 0.7
    max_tokens: int = 2048

    # ========== DATABASE CONFIGURATION ==========
    database_url: str = "postgresql://postgres:postgres@localhost:5432/jorge_bots"
    redis_url: str = "redis://localhost:6379/0"

    # Redis Configuration
    redis_max_connections: int = 50
    redis_min_connections: int = 10
    redis_socket_timeout: int = 2
    redis_socket_connect_timeout: int = 2
    redis_health_check_interval: int = 30

    # ========== PERFORMANCE REQUIREMENTS ==========
    # 5-Minute Response Rule (NON-NEGOTIABLE)
    lead_response_timeout_seconds: int = 300  # 5 minutes = 10x conversion
    lead_analysis_timeout_ms: int = 500  # <500ms for lead analysis
    cma_generation_timeout_seconds: int = 90  # <90 seconds for CMA

    # ========== JORGE'S BUSINESS RULES ==========
    jorge_min_price: int = 200000
    jorge_max_price: int = 800000
    jorge_service_areas: str = "Dallas,Plano,Frisco,McKinney,Allen"
    jorge_preferred_timeline: int = 60  # days
    jorge_standard_commission: float = 0.06  # 6%
    jorge_minimum_commission: float = 0.04  # 4%

    # ========== APPLICATION SETTINGS ==========
    environment: str = "development"
    log_level: str = "INFO"
    app_name: str = "Jorge's Real Estate AI Bots"
    version: str = "1.0.0"
    debug: bool = False

    # ========== SECURITY ==========
    jwt_secret: str = "change_this_in_production"
    ghl_webhook_secret: Optional[str] = None
    ghl_webhook_public_key: Optional[str] = None

    # API Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000

    # ========== WEBHOOK CONFIGURATION ==========
    base_url: str = "http://localhost:8000"

    # ========== BUYER BOT CONFIGURATION ==========
    buyer_pipeline_id: Optional[str] = None
    buyer_alert_workflow_id: Optional[str] = None

    # ========== MULTI-TENANT (Phase 2) ==========
    multi_tenant_enabled: bool = False
    default_tenant_id: Optional[str] = None

    # ========== TESTING ==========
    use_mock_llm: bool = False
    test_mode: bool = False

    # ========== MONITORING (Optional) ==========
    sentry_dsn: Optional[str] = None
    datadog_api_key: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"
    )

    def get_service_areas_list(self) -> list[str]:
        """Get Jorge's service areas as a list."""
        return [area.strip() for area in self.jorge_service_areas.split(",")]

    def is_in_service_area(self, city: str) -> bool:
        """Check if a city is in Jorge's service area."""
        return city.strip() in self.get_service_areas_list()

    def is_in_price_range(self, price: float) -> bool:
        """Check if a price is in Jorge's target range."""
        return self.jorge_min_price <= price <= self.jorge_max_price


# Global settings instance
settings = Settings()
