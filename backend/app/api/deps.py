from typing import Annotated

from fastapi import Depends, Query

from app.repositories.analysis_repository import get_repository
from app.services.analytics_service import AnalyticsService, Filters


def get_service() -> AnalyticsService:
    return AnalyticsService(get_repository())


def get_filters(
    language: Annotated[str | None, Query()] = None,
    sentiment: Annotated[str | None, Query()] = None,
    intent: Annotated[str | None, Query()] = None,
    resolution: Annotated[str | None, Query()] = None,
    risk: Annotated[str | None, Query()] = None,
) -> Filters:
    return Filters(language, sentiment, intent, resolution, risk)


ServiceDep = Annotated[AnalyticsService, Depends(get_service)]
FiltersDep = Annotated[Filters, Depends(get_filters)]
