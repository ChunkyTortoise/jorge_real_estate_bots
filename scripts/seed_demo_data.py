#!/usr/bin/env python3
"""
Seed demo data into the Jorge Bots database (SQLite or PostgreSQL).

Called by jorge_launcher.py --demo. Expects DATABASE_URL already set in env.
Creates tables and inserts 50 leads, conversations, contacts, and properties.
"""
from __future__ import annotations

import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root on sys.path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import JSON, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles


# Map PostgreSQL JSONB → generic JSON so SQLite can create the tables
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(JSON(), **kw)

from database.base import Base
from database.models import (
    ContactModel,
    ConversationModel,
    DealModel,
    LeadModel,
    PropertyModel,
)

# ---------------------------------------------------------------------------
# Data pools for realistic Rancho Cucamonga demo data
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "Maria", "Jose", "David", "Jennifer", "Michael", "Angela", "Robert",
    "Linda", "Carlos", "Patricia", "James", "Sarah", "Daniel", "Lisa",
    "William", "Karen", "Richard", "Nancy", "Thomas", "Sandra", "Kevin",
    "Ashley", "Brian", "Stephanie", "Mark", "Rebecca", "Steven", "Laura",
    "Paul", "Michelle", "Andrew", "Kimberly", "George", "Donna", "Frank",
    "Carol", "Ray", "Amanda", "Peter", "Debra", "Tony", "Teresa", "Alex",
    "Christine", "Victor", "Rachel", "Henry", "Diana", "Oscar", "Gloria",
]

LAST_NAMES = [
    "Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Perez", "Sanchez", "Ramirez", "Torres", "Flores", "Rivera", "Chen",
    "Wang", "Kim", "Patel", "Nguyen", "Johnson", "Williams", "Brown",
    "Smith", "Jones", "Davis", "Miller", "Wilson", "Moore", "Taylor",
    "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Lee",
    "Thompson", "Clark", "Lewis", "Robinson", "Walker", "Young",
]

STREETS = [
    "Foothill Blvd", "Haven Ave", "Baseline Rd", "Archibald Ave",
    "Day Creek Blvd", "Milliken Ave", "Carnelian St", "Hermosa Ave",
    "East Ave", "Vineyard Ave", "Rochester Ave", "Etiwanda Ave",
    "Banyan St", "Church St", "Sapphire St", "Amethyst Ave",
    "Arrow Route", "Highland Ave", "Lemon Ave", "Hellman Ave",
    "Beryl St", "Feron Blvd", "Terra Vista Pkwy", "Victoria Gardens Ln",
]

CITIES = [
    "Rancho Cucamonga", "Rancho Cucamonga", "Rancho Cucamonga",  # weighted
    "Upland", "Ontario", "Fontana", "Claremont",
]

TIMELINES = ["0-30 days", "1-3 months", "3-6 months", "6+ months"]
TEMPERATURES = ["hot", "warm", "cold"]
BOT_TYPES = ["lead_bot", "seller_bot", "buyer_bot"]
STAGES = ["Q0", "Q1", "Q2", "Q3", "Q4", "QUALIFIED", "STALLED"]
DEAL_STATUSES = ["active", "pending", "closed", "lost"]
PROPERTY_STATUSES = ["active", "pending", "sold", "withdrawn"]


def _uid() -> str:
    return str(uuid.uuid4())


def _rand_date(days_back: int = 90) -> datetime:
    delta = timedelta(days=random.randint(0, days_back))
    return datetime.now(timezone.utc) - delta


def _phone() -> str:
    return f"+1909{random.randint(1000000, 9999999)}"


def _email(first: str, last: str) -> str:
    domain = random.choice(["gmail.com", "yahoo.com", "outlook.com", "icloud.com"])
    return f"{first.lower()}.{last.lower()}{random.randint(1, 99)}@{domain}"


def _address() -> str:
    return f"{random.randint(100, 19999)} {random.choice(STREETS)}"


# ---------------------------------------------------------------------------
# Generate records
# ---------------------------------------------------------------------------


def _generate_contacts(n: int = 50) -> list[dict]:
    contacts = []
    for _ in range(n):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        contacts.append({
            "id": _uid(),
            "contact_id": f"ghl_{_uid()[:8]}",
            "location_id": "demo-location-id",
            "name": f"{first} {last}",
            "email": _email(first, last),
            "phone": _phone(),
            "created_at": _rand_date(),
            "updated_at": datetime.now(timezone.utc),
        })
    return contacts


def _generate_leads(contacts: list[dict]) -> list[dict]:
    leads = []
    for c in contacts:
        temp = random.choice(TEMPERATURES)
        score = {
            "hot": random.uniform(70, 100),
            "warm": random.uniform(40, 69),
            "cold": random.uniform(5, 39),
        }[temp]
        leads.append({
            "id": _uid(),
            "contact_id": c["contact_id"],
            "location_id": c["location_id"],
            "score": round(score, 1),
            "temperature": temp,
            "budget_min": random.choice([300_000, 400_000, 500_000, 600_000]),
            "budget_max": random.choice([600_000, 750_000, 900_000, 1_200_000]),
            "timeline": random.choice(TIMELINES),
            "service_area_match": random.random() > 0.2,
            "is_qualified": temp == "hot",
            "metadata_json": {},
            "created_at": c["created_at"],
            "updated_at": datetime.now(timezone.utc),
        })
    return leads


def _generate_conversations(contacts: list[dict], n: int = 35) -> list[dict]:
    convos = []
    sample = random.sample(contacts, min(n, len(contacts)))
    for c in sample:
        bot = random.choice(BOT_TYPES)
        stage = random.choice(STAGES)
        q_num = STAGES.index(stage) if stage in STAGES[:5] else 4
        convos.append({
            "id": _uid(),
            "contact_id": c["contact_id"],
            "bot_type": bot,
            "stage": stage,
            "temperature": random.choice(TEMPERATURES),
            "current_question": q_num,
            "questions_answered": max(0, q_num),
            "is_qualified": stage == "QUALIFIED",
            "conversation_history": [],
            "extracted_data": {"source": "demo_seed"},
            "last_activity": _rand_date(14),
            "conversation_started": c["created_at"],
            "metadata_json": {},
            "created_at": c["created_at"],
            "updated_at": datetime.now(timezone.utc),
        })
    return convos


def _generate_properties(n: int = 20) -> list[dict]:
    props = []
    for _ in range(n):
        city = random.choice(CITIES)
        props.append({
            "id": _uid(),
            "mls_id": f"MLS-{random.randint(100000, 999999)}",
            "address": _address(),
            "city": city,
            "state": "CA",
            "zip": random.choice(["91701", "91730", "91737", "91739"]),
            "price": random.randint(450_000, 1_500_000),
            "beds": random.choice([2, 3, 3, 4, 4, 5]),
            "baths": random.choice([1.0, 2.0, 2.5, 3.0]),
            "sqft": random.randint(1200, 4000),
            "status": random.choice(PROPERTY_STATUSES),
            "listed_at": _rand_date(60),
            "metadata_json": {},
            "created_at": _rand_date(60),
        })
    return props


def _generate_deals(contacts: list[dict], n: int = 8) -> list[dict]:
    deals = []
    sample = random.sample(contacts, min(n, len(contacts)))
    for c in sample:
        status = random.choice(DEAL_STATUSES)
        commission = round(random.uniform(8_000, 35_000), 2) if status == "closed" else None
        deals.append({
            "id": _uid(),
            "contact_id": c["contact_id"],
            "opportunity_id": f"opp_{_uid()[:8]}",
            "status": status,
            "commission": commission,
            "closed_at": _rand_date(30) if status == "closed" else None,
            "created_at": c["created_at"],
            "updated_at": datetime.now(timezone.utc),
            "metadata_json": {},
        })
    return deals


# ---------------------------------------------------------------------------
# Seed entrypoint
# ---------------------------------------------------------------------------

MODEL_MAP = {
    ContactModel: _generate_contacts,
    LeadModel: None,  # depends on contacts
    ConversationModel: None,
    PropertyModel: _generate_properties,
    DealModel: None,
}


async def seed() -> None:
    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///.demo_data/jorge_demo.db")

    # Ensure aiosqlite driver for SQLite URLs
    if db_url.startswith("sqlite://"):
        db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    # Ensure parent directory exists for file-based SQLite
    if "sqlite" in db_url:
        # Extract path after sqlite+aiosqlite:///
        db_path = db_url.split("///", 1)[-1] if "///" in db_url else None
        if db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Check if data already seeded
    async with factory() as session:
        result = await session.execute(text("SELECT count(*) FROM leads"))
        count = result.scalar()
        if count and count > 0:
            print(f"  Database already has {count} leads -- skipping seed")
            return

    # Generate data
    contacts = _generate_contacts(50)
    leads = _generate_leads(contacts)
    conversations = _generate_conversations(contacts, 35)
    properties = _generate_properties(20)
    deals = _generate_deals(contacts, 8)

    async with factory() as session:
        async with session.begin():
            for c in contacts:
                session.add(ContactModel(**c))
            for lead in leads:
                session.add(LeadModel(**lead))
            for conv in conversations:
                session.add(ConversationModel(**conv))
            for prop in properties:
                session.add(PropertyModel(**prop))
            for deal in deals:
                session.add(DealModel(**deal))

    await engine.dispose()

    print(f"  Seeded: {len(contacts)} contacts, {len(leads)} leads, "
          f"{len(conversations)} conversations, {len(properties)} properties, "
          f"{len(deals)} deals")


if __name__ == "__main__":
    asyncio.run(seed())
