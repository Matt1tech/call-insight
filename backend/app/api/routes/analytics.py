from typing import Any

from fastapi import APIRouter

from app.api.deps import FiltersDep, ServiceDep

router = APIRouter(prefix="/analytics")


@router.get("/overview")
async def overview(service: ServiceDep, f: FiltersDep) -> dict[str, Any]:
    return service.overview(f)


@router.get("/resolution")
async def resolution(service: ServiceDep, f: FiltersDep) -> dict[str, Any]:
    return service.resolution(f)


@router.get("/risks")
async def risks(service: ServiceDep, f: FiltersDep) -> dict[str, Any]:
    return service.risks(f)


@router.get("/knowledge-gaps")
async def knowledge_gaps(service: ServiceDep, f: FiltersDep) -> dict[str, Any]:
    return service.knowledge_gaps(f)
