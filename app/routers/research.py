from fastapi import APIRouter, Request, HTTPException

from app.models.schemas import ResearchRequest

router = APIRouter(prefix="/api/research", tags=["research"])


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