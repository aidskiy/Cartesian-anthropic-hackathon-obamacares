from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.models import call_store
from app.models.schemas import CallStatus

router = APIRouter(prefix="/api/reports", tags=["reports"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def reports_page(request: Request):
    completed = [
        r for r in call_store.values() if r.status == CallStatus.completed
    ]
    return templates.TemplateResponse(
        "reports.html", {"request": request, "reports": completed}
    )
