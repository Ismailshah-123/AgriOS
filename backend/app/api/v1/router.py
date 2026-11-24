from fastapi import APIRouter

from app.agents.router import router as agents_router
from app.api.v1.endpoints import health
from app.crop_health.assistant_router import router as assistant_router
from app.crop_health.review_router import router as review_router
from app.crop_health.router import router as crop_health_router
from app.dashboard.router import router as dashboard_router
from app.economics.router import router as economics_router
from app.farms.router import router as farms_router
from app.identity.router import router as identity_router
from app.irrigation.router import router as irrigation_router
from app.knowledge.router import router as knowledge_router
from app.knowledge.router_admin import router as knowledge_admin_router
from app.nutrients.router import router as nutrients_router
from app.soil.router import router as soil_router
from app.weather.router import router as weather_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(identity_router)
api_router.include_router(farms_router)
api_router.include_router(dashboard_router)
api_router.include_router(crop_health_router)
api_router.include_router(assistant_router)
api_router.include_router(weather_router)
api_router.include_router(soil_router)
api_router.include_router(irrigation_router)
api_router.include_router(agents_router)
api_router.include_router(economics_router)
api_router.include_router(review_router)
api_router.include_router(nutrients_router)
api_router.include_router(knowledge_router)
api_router.include_router(knowledge_admin_router)
