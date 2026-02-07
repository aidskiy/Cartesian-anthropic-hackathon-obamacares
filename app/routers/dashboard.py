from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.models import call_store
from app.models.schemas import PhishingScenario

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    scenarios = [{"value": s.value, "label": s.value.replace("_", " ").title()} for s in PhishingScenario]
    active_calls = [
        r for r in call_store.values()
        if r.status.value not in ("completed", "failed")
    ]
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "scenarios": scenarios,
        "active_calls": active_calls,
    })


@router.get("/research", response_class=HTMLResponse)
async def research_page(request: Request):
    scenarios = [{"value": s.value, "label": s.value.replace("_", " ").title()} for s in PhishingScenario]
    return templates.TemplateResponse("research.html", {
        "request": request,
        "scenarios": scenarios,
    })


@router.get("/calls/{call_id}", response_class=HTMLResponse)
async def call_detail(call_id: str, request: Request):
    record = call_store.get(call_id)
    if not record:
        return HTMLResponse("<h1>Call not found</h1>", status_code=404)
    return templates.TemplateResponse("call_detail.html", {
        "request": request,
        "call": record,
    })
