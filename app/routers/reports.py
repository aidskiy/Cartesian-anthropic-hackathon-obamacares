from fastapi import APIRouter

from app.models import call_store
from app.models.schemas import CallStatus

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/")
async def list_reports():
    """JSON list of completed assessment reports."""
    return [
        {
            "id": r.id,
            "target": r.request.target_name,
            "company": r.request.company,
            "scenario": r.request.scenario.value,
            "created_at": r.created_at.isoformat(),
            "notion_url": r.notion_page_url,
        }
        for r in call_store.values()
        if r.status == CallStatus.completed
    ]
