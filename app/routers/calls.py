import uuid
import logging

from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.models.schemas import CallRequest, CallRecord, CallStatus
from app.models import call_store

router = APIRouter(prefix="/api/calls", tags=["calls"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")
logger = logging.getLogger(__name__)


async def process_call(call_id: str, request: Request):
    """Background task that orchestrates the full call flow."""
    record = call_store[call_id]
    llm = request.app.state.llm
    cartesia = request.app.state.cartesia
    researcher = request.app.state.researcher
    notion = request.app.state.notion

    try:
        # Step 1: Research (if enabled)
        research_context = ""
        if record.request.run_research:
            record.status = CallStatus.researching
            research = await researcher.research_target(
                target_name=record.request.target_name,
                company=record.request.company,
                scenario=record.request.scenario,
            )
            research.synthesis = await llm.synthesize_research(
                raw_findings=research.raw_findings,
                target_name=record.request.target_name,
                scenario=record.request.scenario,
            )
            record.research = research
            research_context = research.synthesis

        # Step 2: Generate phishing script
        record.status = CallStatus.generating_script
        script = await llm.generate_phishing_script(
            scenario=record.request.scenario,
            target_name=record.request.target_name,
            company=record.request.company,
            research_context=research_context,
        )
        record.script = script

        # Step 3: Initiate call via Cartesia
        record.status = CallStatus.calling
        phone_numbers = await cartesia.list_phone_numbers()
        from_number = phone_numbers[0]["phone_number"] if phone_numbers else ""

        call_result = await cartesia.initiate_call(
            to_number=record.request.phone_number,
            from_number=from_number,
            system_prompt=script.system_prompt,
            introduction=script.introduction,
            context_metadata={
                "dashboard_call_id": call_id,
                "system_prompt": script.system_prompt,
                "introduction": script.introduction,
            },
        )
        record.cartesia_call_id = call_result.get("id", "")
        record.status = CallStatus.in_progress

    except Exception as e:
        logger.exception(f"Call processing failed for {call_id}")
        record.status = CallStatus.failed
        record.error = str(e)


@router.post("/initiate")
async def initiate_call(
    call_req: CallRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    call_id = str(uuid.uuid4())
    record = CallRecord(id=call_id, request=call_req)
    call_store[call_id] = record

    background_tasks.add_task(process_call, call_id, request)

    return {"call_id": call_id, "status": record.status.value}


@router.get("/{call_id}/status")
async def get_call_status(call_id: str, request: Request):
    record = call_store.get(call_id)
    if not record:
        raise HTTPException(status_code=404, detail="Call not found")

    # If call is in progress, try to update from Cartesia
    if record.status == CallStatus.in_progress and record.cartesia_call_id:
        try:
            cartesia = request.app.state.cartesia
            call_data = await cartesia.get_call(record.cartesia_call_id)
            cartesia_status = call_data.get("status", "")
            if cartesia_status in ("completed", "ended"):
                record.status = CallStatus.completed
                # Fetch final transcript
                record.transcript = await cartesia.get_transcript(
                    record.cartesia_call_id
                )
        except Exception:
            pass

    return HTMLResponse(f"""
        <div id="call-status" hx-get="/api/calls/{call_id}/status" hx-trigger="every 2s" hx-swap="outerHTML">
            <span class="status-badge status-{record.status.value}">{record.status.value.replace('_', ' ').title()}</span>
            {f'<p style="color: var(--pico-del-color);">{record.error}</p>' if record.error else ''}
        </div>
    """)


@router.get("/{call_id}/transcript")
async def get_call_transcript(call_id: str, request: Request):
    record = call_store.get(call_id)
    if not record:
        raise HTTPException(status_code=404, detail="Call not found")

    # Try to get live transcript if call is active
    if record.cartesia_call_id and not record.transcript:
        try:
            cartesia = request.app.state.cartesia
            record.transcript = await cartesia.get_transcript(
                record.cartesia_call_id
            )
        except Exception:
            pass

    transcript = record.transcript or "Waiting for call to begin..."
    trigger = 'hx-trigger="every 3s"' if record.status not in (CallStatus.completed, CallStatus.failed) else ''

    return HTMLResponse(f"""
        <div id="transcript" hx-get="/api/calls/{call_id}/transcript" {trigger} hx-swap="outerHTML">
            <div class="transcript-box">{transcript}</div>
        </div>
    """)


@router.get("/{call_id}/context")
async def get_call_context(call_id: str):
    """Endpoint called by the voice agent to get research context mid-call."""
    record = call_store.get(call_id)
    if not record:
        raise HTTPException(status_code=404, detail="Call not found")

    context = ""
    if record.research and record.research.synthesis:
        context = record.research.synthesis
    if record.request.additional_context:
        context += f"\n\nAdditional context: {record.request.additional_context}"

    return {"context": context}


@router.post("/{call_id}/complete")
async def complete_call(call_id: str, request: Request):
    """Mark a call as completed and generate the report."""
    record = call_store.get(call_id)
    if not record:
        raise HTTPException(status_code=404, detail="Call not found")

    llm = request.app.state.llm
    notion = request.app.state.notion

    try:
        # Fetch final transcript if not yet available
        if record.cartesia_call_id and not record.transcript:
            cartesia = request.app.state.cartesia
            record.transcript = await cartesia.get_transcript(record.cartesia_call_id)

        # Generate report
        research_context = ""
        if record.research:
            research_context = record.research.synthesis

        record.report_markdown = await llm.generate_report(
            target_name=record.request.target_name,
            company=record.request.company,
            scenario=record.request.scenario,
            transcript=record.transcript or "No transcript available",
            research_context=research_context,
        )

        # Write to Notion
        if notion.parent_page_id:
            title = f"Phishing Assessment - {record.request.target_name} ({record.request.scenario.value})"
            record.notion_page_url = await notion.create_call_report(
                title=title,
                target_name=record.request.target_name,
                company=record.request.company,
                scenario=record.request.scenario.value,
                research_context=research_context,
                transcript=record.transcript or "",
                report_markdown=record.report_markdown,
            )

        record.status = CallStatus.completed
        return {"status": "completed", "notion_url": record.notion_page_url}

    except Exception as e:
        logger.exception(f"Report generation failed for {call_id}")
        record.error = str(e)
        return {"status": "error", "error": str(e)}


@router.get("/")
async def list_calls():
    return [
        {
            "id": r.id,
            "target": r.request.target_name,
            "company": r.request.company,
            "scenario": r.request.scenario.value,
            "status": r.status.value,
            "created_at": r.created_at.isoformat(),
        }
        for r in call_store.values()
    ]
