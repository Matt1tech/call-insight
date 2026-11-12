from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import FiltersDep, ServiceDep
from app.services.analytics_service import allowed_filters

router = APIRouter()


@router.get("/filters")
async def filters() -> dict[str, list[str]]:
    return allowed_filters()


@router.get("/conversations")
async def list_conversations(service: ServiceDep, f: FiltersDep) -> list[dict[str, Any]]:
    return service.conversations(f)


@router.get("/conversations/{call_id}")
async def get_conversation(call_id: str, service: ServiceDep) -> dict[str, Any]:
    record = service.conversation(call_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Conversation {call_id} not found")
    return record
