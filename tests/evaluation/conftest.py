import pytest

from bots.seller_bot.jorge_seller_bot import SellerQualificationState
from bots.buyer_bot.buyer_bot import BuyerQualificationState


@pytest.fixture
def seller_state():
    return SellerQualificationState(contact_id="test-123", location_id="loc-456")


@pytest.fixture
def buyer_state():
    return BuyerQualificationState(contact_id="test-789", location_id="loc-456")
