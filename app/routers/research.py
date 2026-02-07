from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.models.schemas import ResearchRequest

router = APIRouter(prefix="/api/research", tags=["research"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def research_page(request: Request):
    from app.models.schemas import PhishingScenario

    scenarios = [{"value": s.value, "label": s.value.replace("_", " ").title()} for s in PhishingScenario]
    return templates.TemplateResponse("research.html", {"request": request, "scenarios": scenarios})


@router.post("/run")
async def run_research(req: ResearchRequest, request: Request):
    researcher = request.app.state.researcher
    llm = request.app.state.llm

    try:
        result = await researcher.research_target(
            target_name=req.target_name,
            company=req.company,
            scenario=req.scenario,
            additional_queries=req.additional_queries,
        )

        result.synthesis = await llm.synthesize_research(
            raw_findings=result.raw_findings,
            target_name=req.target_name,
            scenario=req.scenario,
        )

        return {
            "target_name": result.target_name,
            "company": result.company,
            "scenario": result.scenario.value,
            "synthesis": result.synthesis,
            "queries_run": result.queries_run,
            "raw_count": len(result.raw_findings),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
