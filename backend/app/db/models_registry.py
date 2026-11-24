"""Import every ORM model here so Alembic autogenerate and the drift test see the full
metadata. Add each new module's models in the same change that creates them."""

from app.agents.models import AgentAction, AgentRun, AgentStep
from app.audit.models import AuditEvent
from app.crop_health.models import (
    CaseImage,
    CaseSubmission,
    CropHealthAnalysis,
    CropHealthCase,
    ExpertReview,
)
from app.economics.models import Expense, HarvestSale
from app.farms.models import CropCycle, CropDefinition, Farm, Field
from app.identity.models import RefreshToken, User
from app.jobs.models import Job
from app.knowledge.models import (
    KnowledgeChunk,
    KnowledgeConversation,
    KnowledgeQuery,
    KnowledgeSource,
)
from app.mlops.models import ModelVersion
from app.soil.models import SoilObservation
from app.weather.models import WeatherSnapshot

__all__ = [
    "AgentAction",
    "AgentRun",
    "AgentStep",
    "AuditEvent",
    "CaseImage",
    "CaseSubmission",
    "CropHealthAnalysis",
    "CropHealthCase",
    "Expense",
    "ExpertReview",
    "HarvestSale",
    "Job",
    "KnowledgeChunk",
    "KnowledgeConversation",
    "KnowledgeQuery",
    "KnowledgeSource",
    "ModelVersion",
    "CropCycle",
    "CropDefinition",
    "Farm",
    "Field",
    "RefreshToken",
    "SoilObservation",
    "User",
    "WeatherSnapshot",
]
