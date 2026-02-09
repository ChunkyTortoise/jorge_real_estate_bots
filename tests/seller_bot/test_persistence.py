"""
Tests for Seller Bot Redis Persistence.

Tests the Redis-backed state management for seller bot conversations,
including save, load, and active conversations listing.
"""
from dataclasses import asdict
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from bots.seller_bot.jorge_seller_bot import SellerBotService, SellerQualificationState


@pytest.fixture
def mock_cache_service():
    """Mock CacheService for testing."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def sample_seller_state():
    """Sample seller qualification state for testing."""
    return SellerQualificationState(
        contact_id="test_contact_123",
        location_id="test_location_456",
        current_question=2,
        questions_answered=2,
        conversation_history=[
            {"role": "assistant", "content": "Hello! I'm Jorge."},
            {"role": "user", "content": "Hi, I want to sell my house."},
        ],
        extracted_data={
            "property_condition": "Good",
            "price_expectation": "$450,000"
        },
        stage="Q2",
        last_interaction=datetime.now(),
        conversation_started=datetime(2026, 1, 20, 10, 0, 0)
    )


@pytest.fixture
def seller_bot_service(mock_cache_service):
    """Create SellerBotService with mocked cache."""
    with patch('bots.seller_bot.jorge_seller_bot.get_cache_service', return_value=mock_cache_service):
        service = SellerBotService()
        service.cache = mock_cache_service
        return service


class TestSellerBotPersistence:
    """Test suite for seller bot persistence functionality."""

    @pytest.mark.asyncio
    async def test_get_conversation_state_exists(self, seller_bot_service, mock_cache_service, sample_seller_state):
        """Test loading existing conversation state from Redis."""
        # Arrange: Mock Redis returning saved state
        state_dict = asdict(sample_seller_state)
        state_dict['last_interaction'] = sample_seller_state.last_interaction.isoformat()
        state_dict['conversation_started'] = sample_seller_state.conversation_started.isoformat()
        mock_cache_service.get.return_value = state_dict

        # Act
        loaded_state = await seller_bot_service.get_conversation_state("test_contact_123")

        # Assert
        assert loaded_state is not None
        assert loaded_state.contact_id == "test_contact_123"
        assert loaded_state.current_question == 2
        assert loaded_state.extracted_data["property_condition"] == "Good"

        # Verify correct Redis key was used
        mock_cache_service.get.assert_called_once_with("seller:state:test_contact_123")

    @pytest.mark.asyncio
    async def test_get_conversation_state_not_exists(self, seller_bot_service, mock_cache_service):
        """Test loading non-existent conversation state returns None."""
        # Arrange: Mock Redis returning None
        mock_cache_service.get.return_value = None

        # Act
        loaded_state = await seller_bot_service.get_conversation_state("nonexistent_contact")

        # Assert
        assert loaded_state is None
        mock_cache_service.get.assert_called_once_with("seller:state:nonexistent_contact")

    @pytest.mark.asyncio
    async def test_save_conversation_state(self, seller_bot_service, mock_cache_service, sample_seller_state):
        """Test saving conversation state to Redis with correct TTL."""
        # Act
        await seller_bot_service.save_conversation_state("test_contact_123", sample_seller_state)

        # Assert
        mock_cache_service.set.assert_called_once()
        call_args = mock_cache_service.set.call_args

        # Verify correct Redis key
        assert call_args[0][0] == "seller:state:test_contact_123"

        # Verify TTL is 7 days (604,800 seconds)
        assert call_args[1]['ttl'] == 604800

        # Verify state data is serialized correctly
        saved_data = call_args[0][1]
        assert saved_data['contact_id'] == "test_contact_123"
        assert saved_data['current_question'] == 2

        # Verify datetime fields are converted to ISO format strings
        assert isinstance(saved_data['last_interaction'], str)
        assert isinstance(saved_data['conversation_started'], str)

    @pytest.mark.asyncio
    async def test_save_conversation_state_adds_to_active_set(self, seller_bot_service, mock_cache_service, sample_seller_state):
        """Test that saving state adds contact_id to active contacts set."""
        # Mock sadd for Redis set operation
        mock_cache_service.sadd = AsyncMock(return_value=True)

        # Act
        await seller_bot_service.save_conversation_state("test_contact_123", sample_seller_state)

        # Assert: Verify contact was added to active set
        if hasattr(mock_cache_service, 'sadd'):
            mock_cache_service.sadd.assert_called_once_with(
                "seller:active_contacts",
                "test_contact_123"
            )

    @pytest.mark.asyncio
    async def test_get_all_active_conversations_empty(self, seller_bot_service, mock_cache_service):
        """Test getting active conversations when none exist."""
        # Arrange: Mock empty active contacts set
        mock_cache_service.smembers = AsyncMock(return_value=set())

        # Act
        conversations = await seller_bot_service.get_all_active_conversations()

        # Assert
        assert conversations == []
        if hasattr(mock_cache_service, 'smembers'):
            mock_cache_service.smembers.assert_called_once_with("seller:active_contacts")

    @pytest.mark.asyncio
    async def test_get_all_active_conversations_multiple(self, seller_bot_service, mock_cache_service, sample_seller_state):
        """Test getting multiple active conversations."""
        # Arrange: Mock active contacts set with 3 contacts
        mock_cache_service.smembers = AsyncMock(return_value={"contact_1", "contact_2", "contact_3"})

        # Mock get_conversation_state to return states for each contact
        async def mock_get_state(contact_id):
            state = SellerQualificationState(
                contact_id=contact_id,
                location_id="test_location",
                current_question=1,
                questions_answered=1,
                conversation_history=[],
                extracted_data={},
                stage="Q1",
                last_interaction=datetime.now(),
                conversation_started=datetime.now()
            )
            return state

        seller_bot_service.get_conversation_state = AsyncMock(side_effect=mock_get_state)

        # Act
        conversations = await seller_bot_service.get_all_active_conversations()

        # Assert
        assert len(conversations) == 3
        assert all(isinstance(conv, SellerQualificationState) for conv in conversations)
        contact_ids = {conv.contact_id for conv in conversations}
        assert contact_ids == {"contact_1", "contact_2", "contact_3"}

    @pytest.mark.asyncio
    async def test_delete_conversation_state(self, seller_bot_service, mock_cache_service):
        """Test deleting conversation state from Redis."""
        # Arrange
        mock_cache_service.srem = AsyncMock(return_value=True)

        # Act
        await seller_bot_service.delete_conversation_state("test_contact_123")

        # Assert: Verify state was deleted
        mock_cache_service.delete.assert_called_once_with("seller:state:test_contact_123")

        # Assert: Verify contact was removed from active set
        if hasattr(mock_cache_service, 'srem'):
            mock_cache_service.srem.assert_called_once_with(
                "seller:active_contacts",
                "test_contact_123"
            )

    @pytest.mark.asyncio
    async def test_conversation_state_datetime_serialization(self, seller_bot_service, mock_cache_service):
        """Test that datetime fields are properly serialized and deserialized."""
        # Arrange: Create state with datetime fields
        original_state = SellerQualificationState(
            contact_id="test_contact",
            location_id="test_location",
            current_question=0,
            questions_answered=0,
            conversation_history=[],
            extracted_data={},
            stage="Q0",
            last_interaction=datetime(2026, 1, 23, 10, 30, 0),
            conversation_started=datetime(2026, 1, 23, 10, 0, 0)
        )

        # Act: Save and then load the state
        await seller_bot_service.save_conversation_state("test_contact", original_state)

        # Get the saved data from the mock call
        saved_data = mock_cache_service.set.call_args[0][1]

        # Simulate loading by mocking get to return the saved data
        mock_cache_service.get.return_value = saved_data
        loaded_state = await seller_bot_service.get_conversation_state("test_contact")

        # Assert: Datetimes are correctly converted
        assert isinstance(saved_data['last_interaction'], str)
        assert loaded_state.last_interaction == original_state.last_interaction
        assert loaded_state.conversation_started == original_state.conversation_started

    @pytest.mark.asyncio
    async def test_persistence_error_handling(self, seller_bot_service, mock_cache_service, sample_seller_state):
        """Test error handling when Redis operations fail."""
        # Arrange: Mock Redis failure
        mock_cache_service.set.side_effect = Exception("Redis connection error")

        # Act & Assert: Should raise exception or handle gracefully
        with pytest.raises(Exception) as exc_info:
            await seller_bot_service.save_conversation_state("test_contact", sample_seller_state)

        assert "Redis connection error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_active_conversations_with_none_states(self, seller_bot_service, mock_cache_service):
        """Test that get_all_active_conversations skips contacts with no state."""
        # Arrange: Mock active contacts set
        mock_cache_service.smembers = AsyncMock(return_value={"contact_1", "contact_2", "contact_3"})

        # Mock get_conversation_state to return None for some contacts
        async def mock_get_state(contact_id):
            if contact_id == "contact_2":
                return None  # Simulate expired or deleted state
            return SellerQualificationState(
                contact_id=contact_id,
                location_id="test_location",
                current_question=1,
                questions_answered=1,
                conversation_history=[],
                extracted_data={},
                stage="Q1",
                last_interaction=datetime.now(),
                conversation_started=datetime.now()
            )

        seller_bot_service.get_conversation_state = AsyncMock(side_effect=mock_get_state)

        # Act
        conversations = await seller_bot_service.get_all_active_conversations()

        # Assert: Only 2 conversations returned (contact_2 has no state)
        assert len(conversations) == 2
        contact_ids = {conv.contact_id for conv in conversations}
        assert contact_ids == {"contact_1", "contact_3"}
        assert "contact_2" not in contact_ids
