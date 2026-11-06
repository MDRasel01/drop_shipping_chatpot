from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.database import engine, Base

# Import all models to register them on Base metadata
import app.modules.saas.models
import app.modules.knowledge.models
import app.modules.support.models
import app.modules.orchestration.models
import app.modules.notifications.models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables if connected
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"[Warning] DB initialization skipped or deferred: {e}")

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Multi-Tenant AI-Powered Instruction-Driven Customer Support SaaS Backend",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def root_health():
    return {
        "status": "ok",
        "service": "ai-customer-support-saas",
        "version": "1.0.0"
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }

