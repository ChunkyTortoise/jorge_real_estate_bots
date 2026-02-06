"""
Buyer Bot FastAPI Application.
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager

from bots.shared.logger import get_logger
from bots.buyer_bot.buyer_bot import JorgeBuyerBot
from bots.buyer_bot.buyer_routes import router, init_buyer_bot

logger = get_logger(__name__)

buyer_bot = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global buyer_bot
    logger.info("🔥 Starting Buyer Bot...")
    buyer_bot = JorgeBuyerBot()
    init_buyer_bot(buyer_bot)
    logger.info("✅ Buyer Bot ready!")
    yield
    logger.info("🛑 Shutting down Buyer Bot...")


app = FastAPI(
    title="Jorge's Buyer Bot",
    description="Buyer qualification and property matching",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bots.buyer_bot.main:app", host="0.0.0.0", port=8003, reload=True)
