from fastapi import APIRouter
from app.modules.saas.router import router as saas_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.support.router import router as support_router
from app.modules.notifications.router import router as notifications_router

api_v1_router = APIRouter()

api_v1_router.include_router(saas_router)
api_v1_router.include_router(knowledge_router)
api_v1_router.include_router(support_router)
api_v1_router.include_router(notifications_router)

