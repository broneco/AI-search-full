import logging
from fastapi import FastAPI
from app.core.config import settings
from contextlib import asynccontextmanager
from app.api.routes import health, chat, documents, auth, threads, prompts
from app.storage.db import init_db
from app.api.routes import models
from app.api.routes import search_indexes
from app.api.routes import jhu_connection
from app.core.model_config import ModelError
from fastapi.responses import JSONResponse

# Setup logging
logging.basicConfig(
    level=logging.getLevelName(settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up FastAPI application...")
    if settings.JHU_CONNECTION_MODE == 'managed':
        import asyncio
        from app.providers.jhu_managed import managed_connection, reset_managed_connection
        from app.providers.jhu_secrets import JHUConnectionError
        reset_managed_connection()
        try:
            await asyncio.to_thread(managed_connection)
        except JHUConnectionError as error:
            logger.warning('Volitelné JHU připojení není připravené: %s', error.code)
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
                if settings.APP_ENV == "local":
                    raise
    if settings.APP_ENV == "local":
        from app.ingestion.local_demo import seed_local_demo
        from app.storage.db import SessionLocal
        try:
            await seed_local_demo(SessionLocal)
        except Exception:
            logger.exception("Lokální demo se nepodařilo připravit. Zkontroluj modelové nastavení "
                             "v .env.local a restartuj backend; uživatelské dokumenty zůstávají zachované.")
        try:
            from app.storage.vector_store import activate_local_ready_index
            from app.providers.factory import catalog_embedding_provider
            with SessionLocal() as session:
                activate_local_ready_index(session, catalog_embedding_provider(settings.TENANT_ID).profile)
                session.commit()
        except Exception as error:
            logger.warning("Lokální profilový index čeká na migraci: %s. "
                           "Použij migrate_search_vectors.py podle návodu pro slice 3.", error)
    yield
    logger.info("Shutting down FastAPI application...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Full-stack AI Search Application API",
    lifespan=lifespan,
)


@app.exception_handler(ModelError)
async def model_error_handler(request, error: ModelError):
    return JSONResponse(status_code=error.status, content={"detail": str(error), "code": error.code},
                        headers={"X-Model-Error-Code": error.code})

# Enable CORS for local and future production access
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r".*",
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
app.include_router(models.router, prefix="/api/models", tags=["Models"])
app.include_router(jhu_connection.router, prefix="/api/models/connection", tags=["JHU connection"])
app.include_router(search_indexes.router, prefix="/api/search-indexes", tags=["Search indexes"])


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "health_check": "/health",
    }
