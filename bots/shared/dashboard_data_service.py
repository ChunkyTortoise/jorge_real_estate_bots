"""
Dashboard Data Service for Jorge Real Estate AI.

Orchestrates data from multiple sources for dashboard display:
- MetricsService (performance, budget, timeline, commission)
- Seller bot conversation states
- Lead intelligence data
- GHL integration status

Provides unified data access with consistent caching and error handling.
"""
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import asdict

from bots.shared.logger import get_logger
from bots.shared.cache_service import get_cache_service
from bots.shared.metrics_service import get_metrics_service
from bots.shared.dashboard_models import (
    ConversationState,
    ConversationFilters,
    PaginatedConversations,
    ConversationStage,
    Temperature,
)
from sqlalchemy import select
from database.session import AsyncSessionFactory
from database.models import ConversationModel, ContactModel

logger = get_logger(__name__)


class DashboardDataService:
    """
    Orchestrates dashboard data from multiple sources.

    Features:
    - Unified data access for all dashboard components
    - Smart caching with different TTLs per data type
    - Error handling with graceful degradation
    - Pagination and filtering for large datasets
    - Real-time data fetching for active conversations
    """

    def __init__(self):
        """Initialize dashboard data service with dependencies."""
        self.cache_service = get_cache_service()
        self.metrics_service = get_metrics_service()
        logger.info("DashboardDataService initialized")

    # =================================================================
    # Complete Dashboard Data
    # =================================================================

    async def get_complete_dashboard_data(self) -> Dict[str, Any]:
        """
        Get all dashboard data in a single optimized call.

        Returns:
            Complete dashboard data including metrics, conversations, and status

        Cache TTL: 30 seconds (for full page loads)
        """
        cache_key = "dashboard:complete_data"

        try:
            # Try cache first
            cached = await self.cache_service.get(cache_key)
            if cached:
                logger.debug("Complete dashboard data served from cache")
                return cached

            # Fetch all data concurrently for performance
            metrics_task = self.metrics_service.get_dashboard_summary()
            conversations_task = self.get_active_conversations()
            hero_data_task = self._get_hero_dashboard_data()

            # Await all tasks
            metrics_summary, conversations, hero_data = await asyncio.gather(
                metrics_task,
                conversations_task,
                hero_data_task,
                return_exceptions=True
            )

            # Build complete dashboard data
            dashboard_data = {
                'metrics': metrics_summary if not isinstance(metrics_summary, Exception) else None,
                'active_conversations': asdict(conversations) if not isinstance(conversations, Exception) else None,
                'hero_data': hero_data if not isinstance(hero_data, Exception) else None,
                'generated_at': datetime.now().isoformat(),
                'refresh_interval': 30,  # Seconds
                'status': 'success'
            }

            # Cache for 30 seconds
            await self.cache_service.set(
                cache_key,
                dashboard_data,
                ttl=30
            )

            logger.debug("Complete dashboard data generated and cached")
            return dashboard_data

        except Exception as e:
            logger.exception(f"Error getting complete dashboard data: {e}")
            return self._get_fallback_dashboard_data()

    async def get_dashboard_data(self) -> 'DashboardData':
        """
        Get complete dashboard data as structured DashboardData object.

        Returns:
            DashboardData containing hero metrics, active conversations, and performance metrics

        Cache TTL: 30 seconds (for UI components)
        """
        from bots.shared.dashboard_models import (
            DashboardData, HeroMetrics, PerformanceMetrics, PaginatedConversations
        )

        cache_key = "dashboard:structured_data_v3"

        try:
            # Try cache first
            cached = await self.cache_service.get(cache_key)
            if cached:
                logger.debug("Structured dashboard data served from cache")
                return cached

            # Fetch all data concurrently
            hero_task = self._get_hero_metrics()
            conversations_task = self.get_active_conversations(page=1, page_size=50)
            performance_task = self._get_performance_metrics()

            # Await all tasks
            hero_metrics, active_conversations, performance_metrics = await asyncio.gather(
                hero_task,
                conversations_task,
                performance_task,
                return_exceptions=True
            )

            # Handle exceptions with fallback data
            if isinstance(hero_metrics, Exception):
                logger.error(f"Error fetching hero metrics: {hero_metrics}")
                hero_metrics = self._get_fallback_hero_metrics_obj()

            if isinstance(active_conversations, Exception):
                logger.error(f"Error fetching conversations: {active_conversations}")
                active_conversations = await self._get_fallback_conversations()

            if isinstance(performance_metrics, Exception):
                logger.error(f"Error fetching performance metrics: {performance_metrics}")
                performance_metrics = self._get_fallback_performance_metrics_obj()

            # Build DashboardData object
            dashboard_data = DashboardData(
                hero_metrics=hero_metrics,
                active_conversations=active_conversations,
                performance_metrics=performance_metrics
            )

            # Cache for 30 seconds
            await self.cache_service.set(
                cache_key,
                dashboard_data,
                ttl=30
            )

            logger.debug("Structured dashboard data generated and cached")
            return dashboard_data

        except Exception as e:
            logger.exception(f"Error getting dashboard data: {e}")
            # Return fallback DashboardData
            return DashboardData(
                hero_metrics=self._get_fallback_hero_metrics_obj(),
                active_conversations=await self._get_fallback_conversations(),
                performance_metrics=self._get_fallback_performance_metrics_obj()
            )

    # =================================================================
    # Seller Bot Conversation Data
    # =================================================================

    async def get_active_conversations(
        self,
        filters: Optional[ConversationFilters] = None,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedConversations:
        """
        Get active seller bot conversations with filtering and pagination.

        Args:
            filters: Optional filtering criteria
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Paginated conversation states

        Cache TTL: 60 seconds (conversations change frequently)
        """
        # Build cache key with filters
        filter_key = ""
        if filters:
            filter_key = f"_{hash(str(filters.to_dict()))}"

        cache_key = f"dashboard:conversations:p{page}s{page_size}{filter_key}"

        try:
            # Try cache first
            cached = await self.cache_service.get(cache_key)
            if cached:
                logger.debug("Active conversations served from cache")
                return PaginatedConversations(**cached)

            # Generate fresh conversation data
            conversations = await self._fetch_active_conversations(filters, page, page_size)

            # Cache for 1 minute
            await self.cache_service.set(
                cache_key,
                asdict(conversations),
                ttl=60
            )

            logger.debug("Active conversations generated and cached")
            return conversations

        except Exception as e:
            logger.exception(f"Error getting active conversations: {e}")
            return await self._get_fallback_conversations()

    async def get_conversation_summary(self) -> Dict[str, Any]:
        """
        Get conversation summary statistics.

        Returns:
            Conversation counts by stage and temperature

        Cache TTL: 2 minutes (summary data is relatively stable)
        """
        cache_key = "dashboard:conversations:summary"

        try:
            # Try cache first
            cached = await self.cache_service.get(cache_key)
            if cached:
                logger.debug("Conversation summary served from cache")
                return cached

            # Generate fresh summary
            summary = await self._calculate_conversation_summary()

            # Cache for 2 minutes
            await self.cache_service.set(
                cache_key,
                summary,
                ttl=120
            )

            logger.debug("Conversation summary generated and cached")
            return summary

        except Exception as e:
            logger.exception(f"Error getting conversation summary: {e}")
            return self._get_fallback_conversation_summary()

    # =================================================================
    # Hero Metrics Data
    # =================================================================

    async def get_hero_metrics_data(self) -> Dict[str, Any]:
        """
        Get hero metrics for dashboard header.

        Returns:
            Hero metrics including lead counts, revenue, and ROI

        Cache TTL: 5 minutes (hero data updates less frequently)
        """
        cache_key = "dashboard:hero_metrics"

        try:
            # Try cache first
            cached = await self.cache_service.get(cache_key)
            if cached:
                logger.debug("Hero metrics served from cache")
                return cached

            # Generate fresh hero metrics
            hero_data = await self._get_hero_dashboard_data()

            # Cache for 5 minutes
            await self.cache_service.set(
                cache_key,
                hero_data,
                ttl=300
            )

            logger.debug("Hero metrics generated and cached")
            return hero_data

        except Exception as e:
            logger.exception(f"Error getting hero metrics: {e}")
            return self._get_fallback_hero_metrics()

    # =================================================================
    # Performance Analytics Data
    # =================================================================

    async def get_performance_analytics_data(self) -> Dict[str, Any]:
        """
        Get performance analytics data for charts and tables.

        Returns:
            Performance data optimized for dashboard visualization

        Cache TTL: 1 minute (performance data needs to be fresh)
        """
        cache_key = "dashboard:performance_analytics"

        try:
            # Try cache first
            cached = await self.cache_service.get(cache_key)
            if cached:
                logger.debug("Performance analytics served from cache")
                return cached

            # Fetch performance data concurrently
            metrics_task = self.metrics_service.get_performance_metrics()
            cache_stats_task = self.metrics_service.get_cache_statistics()
            cost_savings_task = self.metrics_service.get_cost_savings()

            metrics, cache_stats, cost_savings = await asyncio.gather(
                metrics_task,
                cache_stats_task,
                cost_savings_task,
                return_exceptions=True
            )

            # Build analytics data structure
            analytics_data = {
                'performance_metrics': asdict(metrics) if not isinstance(metrics, Exception) else None,
                'cache_statistics': asdict(cache_stats) if not isinstance(cache_stats, Exception) else None,
                'cost_savings': asdict(cost_savings) if not isinstance(cost_savings, Exception) else None,
                'generated_at': datetime.now().isoformat(),
            }

            # Cache for 1 minute
            await self.cache_service.set(
                cache_key,
                analytics_data,
                ttl=60
            )

            logger.debug("Performance analytics generated and cached")
            return analytics_data

        except Exception as e:
            logger.exception(f"Error getting performance analytics: {e}")
            return self._get_fallback_performance_analytics()

    # =================================================================
    # Private Data Fetching Methods
    # =================================================================

    async def _fetch_active_conversations(
        self,
        filters: Optional[ConversationFilters],
        page: int,
        page_size: int
    ) -> PaginatedConversations:
        """
        Fetch and filter active seller bot conversations from real data.
        
        Integrates with:
        - JorgeSellerBot conversation states
        - Real seller conversation database/storage
        """
        try:
            conversations = []
            async with AsyncSessionFactory() as session:
                stmt = select(ConversationModel, ContactModel).join(
                    ContactModel,
                    ContactModel.contact_id == ConversationModel.contact_id,
                    isouter=True,
                ).where(ConversationModel.bot_type == "seller")

                if filters:
                    if filters.stage:
                        stmt = stmt.where(ConversationModel.stage == filters.stage.value)
                    if filters.temperature:
                        stmt = stmt.where(ConversationModel.temperature == filters.temperature.value)

                result = await session.execute(stmt)
                for conv, contact in result.all():
                    conversations.append(self._map_conversation_row(conv, contact))
            
            if not conversations:
                logger.warning("No conversation data available, using fallback")
                return await self._get_fallback_conversations(filters, page, page_size)

            # Apply filters
            filtered_conversations = conversations
            if filters:
                if filters.stage:
                    filtered_conversations = [c for c in filtered_conversations if c.stage == filters.stage]
                if filters.temperature:
                    filtered_conversations = [c for c in filtered_conversations if c.temperature == filters.temperature]
                if filters.search_term:
                    term = filters.search_term.lower()
                    filtered_conversations = [
                        c for c in filtered_conversations
                        if term in c.seller_name.lower() or (c.property_address and term in c.property_address.lower())
                    ]
                if filters.show_stalled_only:
                    stall_cutoff = datetime.now() - timedelta(hours=48)
                    filtered_conversations = [c for c in filtered_conversations if c.last_activity < stall_cutoff]

            # Sort conversations
            if filters and filters.sort_by == "stage":
                # Sort by stage progression (Q1 -> Q2 -> Q3 -> Q4 -> QUALIFIED)
                stage_order = {
                    ConversationStage.Q1: 1,
                    ConversationStage.Q2: 2,
                    ConversationStage.Q3: 3,
                    ConversationStage.Q4: 4,
                    ConversationStage.QUALIFIED: 5
                }
                filtered_conversations.sort(
                    key=lambda c: stage_order.get(c.stage, 0),
                    reverse=(filters.sort_order == "desc")
                )
            elif filters and filters.sort_by == "temperature":
                temp_order = {"HOT": 3, "WARM": 2, "COLD": 1}
                filtered_conversations.sort(
                    key=lambda c: temp_order.get(c.temperature.value, 0),
                    reverse=(filters.sort_order == "desc")
                )
            else:  # Sort by last_activity (default)
                filtered_conversations.sort(
                    key=lambda c: c.last_activity,
                    reverse=(filters and filters.sort_order == "desc") or True
                )

            # Apply pagination
            total_count = len(filtered_conversations)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_conversations = filtered_conversations[start_idx:end_idx]

            total_pages = (total_count + page_size - 1) // page_size

            return PaginatedConversations(
                conversations=paginated_conversations,
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1
            )
            
        except Exception as e:
            logger.exception(f"Error fetching real active conversations: {e}")
            return await self._get_fallback_conversations(filters, page, page_size)

    def _map_conversation_row(self, conv: ConversationModel, contact: Optional[ContactModel]) -> ConversationState:
        stage_val = conv.stage or "Q0"
        try:
            stage = ConversationStage(stage_val)
        except Exception:
            stage = ConversationStage.Q0

        temp_val = (conv.temperature or "COLD").upper()
        try:
            temperature = Temperature(temp_val)
        except Exception:
            temperature = Temperature.COLD

        extracted = conv.extracted_data or {}
        metadata = conv.metadata_json or {}

        return ConversationState(
            contact_id=conv.contact_id,
            seller_name=(contact.name if contact and contact.name else "Unknown"),
            stage=stage,
            temperature=temperature,
            current_question=conv.current_question or 0,
            questions_answered=conv.questions_answered or 0,
            last_activity=conv.last_activity or datetime.now(),
            conversation_started=conv.conversation_started or datetime.now(),
            is_qualified=bool(conv.is_qualified),
            property_address=metadata.get("property_address"),
            condition=extracted.get("condition"),
            price_expectation=extracted.get("price_expectation"),
            motivation=extracted.get("motivation"),
            urgency=extracted.get("urgency"),
            next_action="Follow up" if not conv.is_qualified else "Schedule call",
            cma_triggered=bool(metadata.get("cma_triggered")),
        )

    async def _fetch_real_conversation_data(self) -> List[ConversationState]:
        """Fetch real seller bot conversation data from PostgreSQL."""
        try:
            result = await self._fetch_active_conversations(
                filters=None, page=1, page_size=10000
            )
            return result.conversations
        except Exception as e:
            logger.exception(f"Error fetching real conversation data: {e}")
            return []

    async def _get_fallback_conversations(
        self,
        filters: Optional[ConversationFilters] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedConversations:
        """Fallback conversation data when real data is unavailable."""
        return PaginatedConversations(
            conversations=[],
            total_count=0,
            page=page,
            page_size=page_size,
            total_pages=0,
            has_next=False,
            has_prev=False
        )

    async def _calculate_conversation_summary(self) -> Dict[str, Any]:
        """Calculate conversation summary statistics."""
        try:
            async with AsyncSessionFactory() as session:
                total_stmt = select(ConversationModel).where(ConversationModel.bot_type == "seller")
                total_result = await session.execute(total_stmt)
                total_active = len(total_result.scalars().all())

            by_stage = await self._count_by_stage()
            by_temperature = await self._count_by_temperature()

            stalled_cutoff = datetime.now() - timedelta(hours=48)
            stalled_count = 0
            async with AsyncSessionFactory() as session:
                stmt = select(ConversationModel).where(
                    ConversationModel.bot_type == "seller",
                    ConversationModel.last_activity.isnot(None),
                    ConversationModel.last_activity < stalled_cutoff,
                )
                result = await session.execute(stmt)
                stalled_count = len(result.scalars().all())

            summary = {
                'total_active': total_active,
                'by_stage': by_stage,
                'by_temperature': by_temperature,
                'avg_response_time_hours': 4.2,
                'cma_requests_today': 0,
                'qualified_this_week': by_stage.get('QUALIFIED', 0),
                'stalled_conversations': stalled_count
            }
            return summary
        except Exception as e:
            logger.exception(f"Error calculating conversation summary: {e}")
            return {
                'total_active': 0,
                'by_stage': {},
                'by_temperature': {},
                'avg_response_time_hours': 0.0,
                'cma_requests_today': 0,
                'qualified_this_week': 0,
                'stalled_conversations': 0
            }

    async def _count_by_stage(self) -> Dict[str, int]:
        async with AsyncSessionFactory() as session:
            stmt = select(ConversationModel.stage)
            result = await session.execute(stmt)
            counts: Dict[str, int] = {}
            for row in result.scalars().all():
                stage = row or "Q0"
                counts[stage] = counts.get(stage, 0) + 1
            return counts

    async def _count_by_temperature(self) -> Dict[str, int]:
        async with AsyncSessionFactory() as session:
            stmt = select(ConversationModel.temperature)
            result = await session.execute(stmt)
            counts: Dict[str, int] = {}
            for row in result.scalars().all():
                temp = (row or "COLD").upper()
                counts[temp] = counts.get(temp, 0) + 1
            return counts

    async def _get_hero_dashboard_data(self) -> Dict[str, Any]:
        """
        Get hero metrics data from real lead and conversation sources.
        
        Integrates with:
        - MetricsService for lead and commission data
        - Seller bot conversation states
        - Performance tracking data
        """
        try:
            # Get real lead data
            lead_data = await self._fetch_lead_data_for_hero_metrics()
            conversation_page = await self._fetch_active_conversations(None, page=1, page_size=1000)
            conversation_data = conversation_page.conversations
            
            if not lead_data:
                logger.warning("No hero data available, using fallback")
                return self._get_fallback_hero_data()
            
            # Calculate real metrics from actual data
            total_leads = len(lead_data)
            qualified_leads = len([l for l in lead_data if l.get('is_qualified', False)])
            hot_leads = len([l for l in lead_data if l.get('temperature') == 'HOT'])
            active_conversations = len(conversation_data)
            
            # Calculate revenue metrics using real commission calculations
            from bots.shared.business_rules import JorgeBusinessRules
            
            commission_30_day = 0
            commission_pipeline = 0
            deal_sizes = []
            
            for lead in lead_data:
                budget_max = lead.get('budget_max', 0)
                is_qualified = lead.get('is_qualified', False)
                temperature = lead.get('temperature', 'COLD')
                
                if budget_max > 0:
                    commission = JorgeBusinessRules.calculate_commission(budget_max)
                    deal_sizes.append(commission)
                    commission_pipeline += commission
                    
                    # Only hot qualified leads count toward 30-day revenue
                    if temperature == 'HOT' and is_qualified:
                        commission_30_day += commission * 0.6  # 60% close rate
            
            # Calculate lead source ROI from actual data
            lead_source_roi = await self._calculate_real_lead_source_roi(lead_data)
            
            # Calculate performance metrics
            avg_deal_size = sum(deal_sizes) / len(deal_sizes) if deal_sizes else 15000
            conversion_rate = (qualified_leads / total_leads) * 100 if total_leads > 0 else 0
            
            # Get response time from performance tracker
            try:
                from bots.shared.performance_tracker import get_performance_tracker
                performance_tracker = get_performance_tracker()
                performance_metrics = await performance_tracker.get_performance_metrics()
                response_time_avg = performance_metrics.ghl_avg_response_time / 1000  # Convert to seconds
            except:
                response_time_avg = 4.2  # Fallback
            
            # Revenue forecast (hot leads * 60% close rate)
            revenue_forecast = commission_30_day + (hot_leads * avg_deal_size * 0.4)
            
            hero_data = {
                'total_leads': total_leads,
                'qualified_leads': qualified_leads,
                'hot_leads': hot_leads,
                'active_conversations': active_conversations,
                'revenue_30_day': int(commission_30_day),
                'revenue_forecast': int(revenue_forecast),
                'lead_source_roi': lead_source_roi,
                'commission_pipeline': int(commission_pipeline),
                'avg_deal_size': int(avg_deal_size),
                'conversion_rate': round(conversion_rate, 1),
                'response_time_avg': round(response_time_avg, 1)
            }
            
            logger.info(f"Generated hero dashboard data from {total_leads} leads and {active_conversations} conversations")
            return hero_data
            
        except Exception as e:
            logger.exception(f"Error getting real hero dashboard data: {e}")
            return self._get_fallback_hero_data()

    async def _fetch_lead_data_for_hero_metrics(self) -> List[Dict[str, Any]]:
        """Fetch lead data for hero metrics calculation."""
        try:
            # Reuse the commission analysis data which has qualification and temperature
            from bots.shared.metrics_service import MetricsService
            metrics_service = MetricsService()
            return await metrics_service._fetch_lead_data_for_commission_analysis()
        except Exception as e:
            logger.exception(f"Error fetching lead data for hero metrics: {e}")
            return []

    async def _calculate_real_lead_source_roi(self, lead_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate ROI for different lead sources from actual lead data."""
        try:
            from bots.shared.business_rules import JorgeBusinessRules

            # Deterministic industry-average cost per lead by source
            cost_per_lead = {
                "referrals": 0,
                "google_ads": 65,
                "facebook": 45,
                "zillow": 125,
            }

            # Group leads by source from metadata_json
            source_buckets: Dict[str, List[Dict[str, Any]]] = {
                src: [] for src in cost_per_lead
            }
            for lead in lead_data:
                meta = lead.get("metadata_json") or {}
                source = meta.get("lead_source", "unknown").lower()
                if source in source_buckets:
                    source_buckets[source].append(lead)
                else:
                    source_buckets.setdefault("unknown", []).append(lead)

            lead_source_roi: Dict[str, Any] = {}
            for source, leads in source_buckets.items():
                if source == "unknown":
                    continue
                lead_count = len(leads)
                cost = lead_count * cost_per_lead.get(source, 0)

                # Revenue from qualified leads using actual commission calc
                revenue = 0.0
                for ld in leads:
                    if ld.get("is_qualified"):
                        budget = ld.get("budget_max") or ld.get("budget_min") or 0
                        if budget > 0:
                            revenue += JorgeBusinessRules.calculate_commission(budget)

                if source == "referrals":
                    roi = "infinite" if revenue > 0 else 0
                else:
                    roi = round(revenue / cost, 1) if cost > 0 else 0

                lead_source_roi[source] = {
                    "roi": roi,
                    "leads": lead_count,
                    "cost": cost,
                }

            # Ensure standard 4 sources always present for backward compat
            for src in cost_per_lead:
                if src not in lead_source_roi:
                    roi_val = "infinite" if src == "referrals" else 0
                    lead_source_roi[src] = {"roi": roi_val, "leads": 0, "cost": 0}

            return lead_source_roi

        except Exception as e:
            logger.exception(f"Error calculating lead source ROI: {e}")
            return {
                'referrals': {'roi': 'infinite', 'leads': 0, 'cost': 0},
                'google_ads': {'roi': 0, 'leads': 0, 'cost': 0},
                'facebook': {'roi': 0, 'leads': 0, 'cost': 0},
                'zillow': {'roi': 0, 'leads': 0, 'cost': 0}
            }

    def _get_fallback_hero_data(self) -> Dict[str, Any]:
        """Fallback hero data when real data is unavailable."""
        return {
            'total_leads': 0,
            'qualified_leads': 0,
            'hot_leads': 0,
            'active_conversations': 0,
            'revenue_30_day': 0,
            'revenue_forecast': 0,
            'lead_source_roi': {
                'referrals': {'roi': 'infinite', 'leads': 0, 'cost': 0},
                'google_ads': {'roi': 0, 'leads': 0, 'cost': 0},
                'facebook': {'roi': 0, 'leads': 0, 'cost': 0},
                'zillow': {'roi': 0, 'leads': 0, 'cost': 0}
            },
            'commission_pipeline': 0,
            'avg_deal_size': 0,
            'conversion_rate': 0,
            'response_time_avg': 0
        }

    # =================================================================
    # Fallback Methods (Error Handling)
    # =================================================================

    def _get_fallback_dashboard_data(self) -> Dict[str, Any]:
        """Return fallback dashboard data when errors occur."""
        return {
            'metrics': None,
            'active_conversations': None,
            'hero_data': None,
            'generated_at': datetime.now().isoformat(),
            'refresh_interval': 30,
            'status': 'error',
            'error': 'Dashboard data temporarily unavailable'
        }

    def _get_fallback_conversation_summary(self) -> Dict[str, Any]:
        """Return fallback conversation summary when errors occur."""
        return {
            'total_active': 0,
            'by_stage': {},
            'by_temperature': {},
            'avg_response_time_hours': 0,
            'cma_requests_today': 0,
            'qualified_this_week': 0,
            'stalled_conversations': 0,
            'error': 'Conversation data temporarily unavailable'
        }

    def _get_fallback_hero_metrics(self) -> Dict[str, Any]:
        """Return fallback hero metrics when errors occur."""
        return {
            'total_leads': 0,
            'qualified_leads': 0,
            'hot_leads': 0,
            'active_conversations': 0,
            'revenue_30_day': 0,
            'revenue_forecast': 0,
            'lead_source_roi': {},
            'commission_pipeline': 0,
            'avg_deal_size': 0,
            'conversion_rate': 0,
            'response_time_avg': 0,
            'error': 'Hero data temporarily unavailable'
        }

    def _get_fallback_performance_analytics(self) -> Dict[str, Any]:
        """Return fallback performance analytics when errors occur."""
        return {
            'performance_metrics': None,
            'cache_statistics': None,
            'cost_savings': None,
            'generated_at': datetime.now().isoformat(),
            'error': 'Performance data temporarily unavailable'
        }

    # =================================================================
    # Structured Data Methods (Phase 3)
    # =================================================================

    async def _get_hero_metrics(self) -> 'HeroMetrics':
        """Get hero metrics as structured HeroMetrics object."""
        from bots.shared.dashboard_models import HeroMetrics

        try:
            # Get current conversation summary
            summary = await self._calculate_conversation_summary()

            # Calculate 24h deltas (simplified - in production, compare with historical data)
            active_count = summary.get('active_count', 0)
            qualified_count = summary.get('qualified_count', 0)
            total_count = summary.get('total_count', 1)

            qualification_rate = qualified_count / total_count if total_count > 0 else 0.0

            # Mock delta calculations (in production, fetch from PerformanceTracker)
            return HeroMetrics(
                active_conversations=active_count,
                active_conversations_change=2,  # Mock: +2 from yesterday
                qualification_rate=qualification_rate,
                qualification_rate_change=0.05,  # Mock: +5% from yesterday
                avg_response_time_minutes=12.5,
                response_time_change=-1.2,  # Mock: -1.2m improvement
                hot_leads_count=summary.get('hot_count', 0),
                hot_leads_change=1  # Mock: +1 hot lead
            )

        except Exception as e:
            logger.exception(f"Error calculating hero metrics: {e}")
            return self._get_fallback_hero_metrics_obj()

    async def _get_performance_metrics(self) -> 'PerformanceMetrics':
        """Get performance metrics as structured PerformanceMetrics object."""
        from bots.shared.dashboard_models import PerformanceMetrics

        try:
            # Get performance data from metrics service
            metrics = await self.metrics_service.get_performance_metrics()

            return PerformanceMetrics(
                qualification_rate=metrics.get('qualification_rate', 0.65),
                avg_response_time=metrics.get('avg_response_time_minutes', 12.5),
                budget_performance=metrics.get('budget_performance', 1.1),
                timeline_performance=metrics.get('timeline_performance', 0.95),
                commission_performance=metrics.get('commission_performance', 1.05)
            )

        except Exception as e:
            logger.exception(f"Error calculating performance metrics: {e}")
            return self._get_fallback_performance_metrics_obj()

    def _get_fallback_hero_metrics_obj(self) -> 'HeroMetrics':
        """Return fallback HeroMetrics when errors occur."""
        from bots.shared.dashboard_models import HeroMetrics

        return HeroMetrics(
            active_conversations=0,
            active_conversations_change=0,
            qualification_rate=0.0,
            qualification_rate_change=0.0,
            avg_response_time_minutes=0.0,
            response_time_change=0.0,
            hot_leads_count=0,
            hot_leads_change=0
        )

    def _get_fallback_performance_metrics_obj(self) -> 'PerformanceMetrics':
        """Return fallback PerformanceMetrics when errors occur."""
        from bots.shared.dashboard_models import PerformanceMetrics

        return PerformanceMetrics(
            qualification_rate=0.0,
            avg_response_time=0.0,
            budget_performance=0.0,
            timeline_performance=0.0,
            commission_performance=0.0
        )


# Global dashboard data service instance
_dashboard_data_service: Optional[DashboardDataService] = None


def get_dashboard_data_service() -> DashboardDataService:
    """Get the global dashboard data service instance."""
    global _dashboard_data_service

    if _dashboard_data_service is None:
        _dashboard_data_service = DashboardDataService()

    return _dashboard_data_service
