from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field


class PhishingScenario(str, Enum):
    bank_fraud = "bank_fraud"
    it_support = "it_support"
    ceo_fraud = "ceo_fraud"
    vendor_invoice = "vendor_invoice"
    hr_benefits = "hr_benefits"


class CallStatus(str, Enum):
    pending = "pending"
    researching = "researching"
    generating_script = "generating_script"
    calling = "calling"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class CallRequest(BaseModel):
    phone_number: str
    target_name: str
    company: str
    scenario: PhishingScenario
    run_research: bool = True
    additional_context: str = ""


class PhishingScript(BaseModel):
    system_prompt: str = ""
    introduction: str = ""
    persona_name: str = ""
    persona_role: str = ""
    key_talking_points: list[str] = Field(default_factory=list)


class ResearchRequest(BaseModel):
    target_name: str
    company: str
    scenario: PhishingScenario
    additional_queries: list[str] = Field(default_factory=list)


class ResearchResult(BaseModel):
    target_name: str
    company: str
    scenario: PhishingScenario
    raw_findings: list[str] = Field(default_factory=list)
    synthesis: str = ""
    queries_run: list[str] = Field(default_factory=list)


class CallRecord(BaseModel):
    id: str
    request: CallRequest
    status: CallStatus = CallStatus.pending
    created_at: datetime = Field(default_factory=datetime.utcnow)
    cartesia_call_id: str | None = None
    research: ResearchResult | None = None
    script: PhishingScript | None = None
    transcript: str | None = None
    report_markdown: str | None = None
    notion_page_url: str | None = None
    error: str | None = None
