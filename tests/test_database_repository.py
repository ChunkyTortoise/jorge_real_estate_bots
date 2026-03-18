"""
Database repository tests.

Tests upsert/fetch operations for Contact, Conversation, and Lead models
using an in-memory SQLite database (aiosqlite) for isolation.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import JSON, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database.base import Base
from database.models import ContactModel, ConversationModel, LeadModel
from database import session as db_session_module
from database import repository as db_repository_module


@pytest.fixture
async def real_db(request):
    """Provide an isolated async SQLite engine with core tables created.

    Patches the module-level session factory so repository helpers use this engine.
    Yields a session factory for assertions.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    # SQLite does not support JSONB; remap to plain JSON for tests
    for model in (ContactModel, ConversationModel, LeadModel):
        for col in model.__table__.columns:
            if hasattr(col.type, "__class__") and col.type.__class__.__name__ == "JSONB":
                col.type = JSON()

    core_tables = [
        ContactModel.__table__,
        ConversationModel.__table__,
        LeadModel.__table__,
    ]

    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=core_tables))

    Session = async_sessionmaker(bind=engine, expire_on_commit=False)

    # Patch module-level session factory so repository helpers use this engine
    prev_engine = db_session_module._async_engine
    prev_factory = db_session_module._session_factory
    prev_repo_factory = db_repository_module.AsyncSessionFactory
    db_session_module._async_engine = engine
    db_session_module._session_factory = Session
    # Also patch the reference imported into the repository module
    db_repository_module.AsyncSessionFactory = Session

    yield Session

    db_session_module._async_engine = prev_engine
    db_session_module._session_factory = prev_factory
    db_repository_module.AsyncSessionFactory = prev_repo_factory

    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, tables=core_tables))
    await engine.dispose()


# ========== CONTACT UPSERT & FETCH ==========


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_contact_creates_new(real_db):
    """upsert_contact creates a new contact when none exists."""
    from database.repository import upsert_contact

    await upsert_contact(
        contact_id="ghl_c1",
        location_id="loc_1",
        name="Jorge Salas",
        email="jorge@example.com",
        phone="+1234567890",
    )

    async with real_db() as session:
        stmt = select(ContactModel).where(ContactModel.contact_id == "ghl_c1")
        result = await session.execute(stmt)
        contact = result.scalars().first()
    assert contact is not None
    assert contact.name == "Jorge Salas"
    assert contact.phone == "+1234567890"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_contact_updates_existing(real_db):
    """upsert_contact updates fields when contact already exists."""
    from database.repository import upsert_contact

    await upsert_contact(contact_id="ghl_c2", name="Original Name")
    await upsert_contact(contact_id="ghl_c2", name="Updated Name", email="new@example.com")

    async with real_db() as session:
        stmt = select(ContactModel).where(ContactModel.contact_id == "ghl_c2")
        result = await session.execute(stmt)
        contact = result.scalars().first()
    assert contact is not None
    assert contact.name == "Updated Name"
    assert contact.email == "new@example.com"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_contact_preserves_existing_fields(real_db):
    """upsert_contact does not overwrite fields with None."""
    from database.repository import upsert_contact

    await upsert_contact(contact_id="ghl_c3", name="Keep Me", email="keep@example.com")
    await upsert_contact(contact_id="ghl_c3", phone="+1111111111")

    async with real_db() as session:
        stmt = select(ContactModel).where(ContactModel.contact_id == "ghl_c3")
        result = await session.execute(stmt)
        contact = result.scalars().first()
    assert contact is not None
    assert contact.name == "Keep Me"
    assert contact.email == "keep@example.com"
    assert contact.phone == "+1111111111"


# ========== CONVERSATION UPSERT & FETCH ==========


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_conversation_creates_new(real_db):
    """upsert_conversation inserts a new row."""
    from database.repository import upsert_conversation

    now = datetime.now(timezone.utc)
    await upsert_conversation(
        contact_id="ghl_c1",
        bot_type="buyer",
        stage="q1",
        temperature="warm",
        current_question=1,
        questions_answered=1,
        is_qualified=False,
        conversation_history=[{"role": "user", "content": "I want to buy"}],
        extracted_data={"budget": 375000},
        last_activity=now,
        conversation_started=now,
    )

    async with real_db() as session:
        stmt = select(ConversationModel).where(
            ConversationModel.contact_id == "ghl_c1",
            ConversationModel.bot_type == "buyer",
        )
        result = await session.execute(stmt)
        conv = result.scalars().first()
    assert conv is not None
    assert conv.stage == "q1"
    assert conv.temperature == "warm"
    assert conv.current_question == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_conversation_updates_existing(real_db):
    """upsert_conversation updates when same contact_id + bot_type exists."""
    from database.repository import upsert_conversation

    now = datetime.now(timezone.utc)
    base = dict(
        contact_id="ghl_c1",
        bot_type="seller",
        temperature="cold",
        current_question=0,
        questions_answered=0,
        is_qualified=False,
        conversation_history=[],
        extracted_data={},
        last_activity=now,
        conversation_started=now,
    )

    await upsert_conversation(stage="q1", **base)
    await upsert_conversation(stage="q3", **{**base, "current_question": 3, "questions_answered": 3})

    async with real_db() as session:
        stmt = select(ConversationModel).where(
            ConversationModel.contact_id == "ghl_c1",
            ConversationModel.bot_type == "seller",
        )
        result = await session.execute(stmt)
        conv = result.scalars().first()
    assert conv is not None
    assert conv.stage == "q3"
    assert conv.current_question == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_conversation_returns_none_when_missing(real_db):
    """fetch_conversation returns None for non-existent contact."""
    from database.repository import fetch_conversation

    result = await fetch_conversation("nonexistent", "buyer")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_conversation_returns_correct_record(real_db):
    """fetch_conversation retrieves the right record."""
    from database.repository import upsert_conversation, fetch_conversation

    now = datetime.now(timezone.utc)
    await upsert_conversation(
        contact_id="ghl_fetch",
        bot_type="buyer",
        stage="q2",
        temperature="hot",
        current_question=2,
        questions_answered=2,
        is_qualified=False,
        conversation_history=[],
        extracted_data={"area": "Miami"},
        last_activity=now,
        conversation_started=now,
    )

    conv = await fetch_conversation("ghl_fetch", "buyer")
    assert conv is not None
    assert conv.stage == "q2"
    assert conv.temperature == "hot"


# ========== JSONB FIELD SERIALIZATION ==========


@pytest.mark.integration
@pytest.mark.asyncio
async def test_conversation_jsonb_stores_and_retrieves_dict(real_db):
    """JSONB extracted_data stores a dict and retrieves it intact."""
    from database.repository import upsert_conversation, fetch_conversation

    now = datetime.now(timezone.utc)
    extracted = {"budget": 500000, "areas": ["Miami", "Fort Lauderdale"], "preapproved": True}
    await upsert_conversation(
        contact_id="ghl_jsonb",
        bot_type="buyer",
        stage="q4",
        temperature="hot",
        current_question=4,
        questions_answered=4,
        is_qualified=True,
        conversation_history=[{"role": "assistant", "content": "Great!"}],
        extracted_data=extracted,
        last_activity=now,
        conversation_started=now,
    )

    conv = await fetch_conversation("ghl_jsonb", "buyer")
    assert conv is not None
    assert conv.extracted_data == extracted
    assert conv.extracted_data["areas"] == ["Miami", "Fort Lauderdale"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_conversation_history_jsonb_round_trip(real_db):
    """conversation_history JSONB field stores list of dicts."""
    from database.repository import upsert_conversation, fetch_conversation

    now = datetime.now(timezone.utc)
    history = [
        {"role": "user", "content": "I want to sell my house"},
        {"role": "assistant", "content": "What is the address?"},
        {"role": "user", "content": "123 Main St"},
    ]
    await upsert_conversation(
        contact_id="ghl_hist",
        bot_type="seller",
        stage="q2",
        temperature="warm",
        current_question=2,
        questions_answered=2,
        is_qualified=False,
        conversation_history=history,
        extracted_data={},
        last_activity=now,
        conversation_started=now,
    )

    conv = await fetch_conversation("ghl_hist", "seller")
    assert conv is not None
    assert len(conv.conversation_history) == 3
    assert conv.conversation_history[2]["content"] == "123 Main St"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_conversation_metadata_json_round_trip(real_db):
    """metadata_json JSONB stores arbitrary metadata."""
    from database.repository import upsert_conversation, fetch_conversation

    now = datetime.now(timezone.utc)
    meta = {"source": "webhook", "q4_attempts": 2, "offer_presented": True}
    await upsert_conversation(
        contact_id="ghl_meta",
        bot_type="buyer",
        stage="q4",
        temperature="hot",
        current_question=4,
        questions_answered=4,
        is_qualified=True,
        conversation_history=[],
        extracted_data={},
        last_activity=now,
        conversation_started=now,
        metadata_json=meta,
    )

    conv = await fetch_conversation("ghl_meta", "buyer")
    assert conv is not None
    assert conv.metadata_json == meta
    assert conv.metadata_json["q4_attempts"] == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_conversation_persists_canonical_fields(real_db):
    """Canonical mode/status/handoff fields persist as first-class columns."""
    from database.repository import upsert_conversation, fetch_conversation

    now = datetime.now(timezone.utc)
    await upsert_conversation(
        contact_id="ghl_canonical",
        bot_type="lead",
        stage="SUPPRESSED",
        temperature="cold",
        current_question=0,
        questions_answered=0,
        is_qualified=False,
        conversation_history=[],
        extracted_data={},
        last_activity=now,
        conversation_started=now,
        metadata_json={"source": "webhook"},
        mode="human_handoff",
        mode_version=1,
        status="suppressed",
        handoff_reason="manual_override",
        human_takeover=True,
        bilingual_required=False,
        message_suppression_reason="manual_override",
        qualification_summary={"reason": "operator takeover"},
        next_recommended_action="Await Jorge follow-up",
        crm_sync_status="pending",
        last_inbound_at=now,
        last_outbound_at=None,
    )

    conv = await fetch_conversation("ghl_canonical", "lead")
    assert conv is not None
    assert conv.mode == "human_handoff"
    assert conv.status == "suppressed"
    assert conv.handoff_reason == "manual_override"
    assert conv.human_takeover is True
    assert conv.message_suppression_reason == "manual_override"
    assert conv.qualification_summary == {"reason": "operator takeover"}
    assert conv.next_recommended_action == "Await Jorge follow-up"


# ========== M1 — qualification_summary can be cleared to {} ==========


@pytest.mark.integration
@pytest.mark.asyncio
async def test_qualification_summary_can_be_cleared(real_db):
    """upsert_conversation should allow clearing qualification_summary to {}."""
    from database.repository import upsert_conversation, fetch_conversation

    now = datetime.now(timezone.utc)

    # First upsert: set non-empty qualification_summary
    await upsert_conversation(
        contact_id="ghl_clear_qs",
        bot_type="seller",
        stage="Q2",
        temperature="warm",
        current_question=2,
        questions_answered=2,
        is_qualified=False,
        conversation_history=[],
        extracted_data={},
        last_activity=now,
        conversation_started=now,
        qualification_summary={"property_condition": "move_in_ready", "price": 350000},
    )

    conv = await fetch_conversation("ghl_clear_qs", "seller")
    assert conv is not None
    assert conv.qualification_summary == {"property_condition": "move_in_ready", "price": 350000}

    # Second upsert: explicitly clear qualification_summary to {}
    await upsert_conversation(
        contact_id="ghl_clear_qs",
        bot_type="seller",
        stage="Q2",
        temperature="warm",
        current_question=2,
        questions_answered=2,
        is_qualified=False,
        conversation_history=[],
        extracted_data={},
        last_activity=now,
        conversation_started=now,
        qualification_summary={},
    )

    conv = await fetch_conversation("ghl_clear_qs", "seller")
    assert conv is not None
    # qualification_summary should be {} (not preserved as the old non-empty value)
    assert conv.qualification_summary == {}


# ========== MERGE CONVERSATION METADATA (M5) ==========


@pytest.mark.integration
@pytest.mark.asyncio
async def test_merge_returns_true_on_success(real_db):
    """merge_conversation_metadata returns True when a matching record exists."""
    from database.repository import merge_conversation_metadata, upsert_conversation
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    await upsert_conversation(
        contact_id="ghl_merge_ok",
        bot_type="seller",
        stage="Q1",
        temperature="warm",
        current_question=1,
        questions_answered=1,
        is_qualified=False,
        conversation_history=[],
        extracted_data={},
        last_activity=now,
        conversation_started=now,
    )

    result = await merge_conversation_metadata(
        "ghl_merge_ok", "seller", {"mode": "seller", "status": "active"}
    )
    assert result is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_merge_returns_false_when_not_found(real_db):
    """merge_conversation_metadata returns False when no record exists."""
    from database.repository import merge_conversation_metadata

    result = await merge_conversation_metadata(
        "ghl_no_such_contact", "seller", {"mode": "seller"}
    )
    assert result is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_merge_updates_fields(real_db):
    """merge_conversation_metadata merges metadata into the existing record."""
    from database.repository import merge_conversation_metadata, fetch_conversation, upsert_conversation
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    await upsert_conversation(
        contact_id="ghl_merge_fields",
        bot_type="seller",
        stage="Q1",
        temperature="warm",
        current_question=1,
        questions_answered=1,
        is_qualified=False,
        conversation_history=[],
        extracted_data={},
        last_activity=now,
        conversation_started=now,
    )

    await merge_conversation_metadata(
        "ghl_merge_fields", "seller", {"mode": "seller", "status": "qualified"}
    )

    conv = await fetch_conversation("ghl_merge_fields", "seller")
    assert conv is not None
    assert conv.mode == "seller"
    assert conv.status == "qualified"


# ========== UPSERT WITH ROW-LEVEL LOCK (C4) ==========


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_with_for_update_no_error(real_db):
    """upsert_conversation with .with_for_update() succeeds and second call overwrites."""
    from database.repository import fetch_conversation, upsert_conversation
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    await upsert_conversation(
        contact_id="ghl_lock_test",
        bot_type="seller",
        stage="Q1",
        temperature="cold",
        current_question=1,
        questions_answered=1,
        is_qualified=False,
        conversation_history=[],
        extracted_data={},
        last_activity=now,
        conversation_started=now,
    )
    await upsert_conversation(
        contact_id="ghl_lock_test",
        bot_type="seller",
        stage="Q2",
        temperature="warm",
        current_question=2,
        questions_answered=2,
        is_qualified=False,
        conversation_history=[],
        extracted_data={},
        last_activity=now,
        conversation_started=now,
    )

    conv = await fetch_conversation("ghl_lock_test", "seller")
    assert conv is not None
    assert conv.stage == "Q2"
    assert conv.temperature == "warm"
