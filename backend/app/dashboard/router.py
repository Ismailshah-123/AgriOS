"""Dashboard overview: one owner-scoped aggregate built from farm-domain records and the
user's own audit trail. No estimated, simulated or generated values."""

from datetime import date

from fastapi import APIRouter

from app.audit import service as audit
from app.dashboard import analytics, intelligence
from app.dashboard.schemas import AnalyticsOut, OverviewOut, RecentChange
from app.farms import overview
from app.identity.deps import AppSettings, CurrentUser, DbSession

router = APIRouter(tags=["dashboard"])

FARM_ENTITIES = ("farm", "field", "crop_cycle")


@router.get("/overview", response_model=OverviewOut)
def get_overview(user: CurrentUser, db: DbSession, settings: AppSettings) -> OverviewOut:
    events = audit.recent_for_actor(db, user.id, FARM_ENTITIES, limit=8)
    names = overview.names_for(
        db, user.id, [(e.entity, e.entity_id) for e in events if e.entity_id is not None]
    )
    return OverviewOut.model_validate(
        {
            "counts": overview.counts(db, user.id),
            "active_cycles": overview.active_cycles(db, user.id),
            "upcoming": overview.upcoming(db, user.id, date.today()),
            "recent_changes": [
                RecentChange(
                    action=e.action,
                    entity=e.entity,  # type: ignore[arg-type]
                    entity_id=e.entity_id,
                    name=names.get(e.entity_id) if e.entity_id else None,
                    created_at=e.created_at,
                )
                for e in events
            ],
            "intelligence": intelligence.summary(db, user.id, settings.model_path),
        }
    )


@router.get("/analytics", response_model=AnalyticsOut)
def get_analytics(user: CurrentUser, db: DbSession) -> AnalyticsOut:
    """Dashboard charts: grouped sums/counts over the caller's own records only."""
    return AnalyticsOut.model_validate(analytics.summary(db, user.id))
