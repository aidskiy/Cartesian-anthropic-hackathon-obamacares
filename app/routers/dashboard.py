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
    all_calls = sorted(call_store.values(), key=lambda r: r.created_at, reverse=True)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "scenarios": scenarios,
        "all_calls": all_calls,
    })
