import logging
from fastapi import FastAPI
from app.core.config import settings
from contextlib import asynccontextmanager
from app.api.routes import health, chat, documents, auth, threads, prompts
from app.storage.db import init_db

# Setup logging
logging.basicConfig(
    level=logging.getLevelName(settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up FastAPI application...")
    for attempt in range(1, 4):
        try:
            init_db()
            logger.info("Database initialization successful.")
            break
        except Exception as e:
            logger.warning(f"Database initialization attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                import asyncio
                await asyncio.sleep(2)
            else:
                logger.error(f"Database initialization failed after 3 attempts: {e}")
    yield
    logger.info("Shutting down FastAPI application...")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Full-stack AI Search Application API",
    lifespan=lifespan,
)

# Enable CORS for local and future production access
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production requirements later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(health.router, prefix="/health", tags=["Health"], include_in_schema=False)
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(threads.router, prefix="/api/threads", tags=["Threads"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(prompts.router, prefix="/api/prompts", tags=["Prompts"])


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": "0.1.0",
        "health_check": "/health",
    }
