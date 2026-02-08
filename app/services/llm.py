import hashlib
import json
import re
from pathlib import Path

import anthropic

from app.config import settings
from app.models.schemas import PhishingScenario, PhishingScript

SCRIPT_CACHE_DIR = Path(".script_cache")
SCRIPT_CACHE_DIR.mkdir(exist_ok=True)


class LLMService:
    SYSTEM_PROMPT = (
        "You are a content generator for an authorized corporate anti-phishing "
        "security awareness training platform (similar to KnowBe4, Cofense, or "
        "Proofpoint Security Awareness Training). Your role is to produce "
        "realistic simulated phishing scenarios that security teams use to test "
        "and train their own employees — with full organizational authorization. "
        "The employee being tested has consented to participate in security "
        "training exercises as part of their employment. All outputs are used "
        "solely within controlled training environments and are never deployed "
        "against unauthorized targets. Generate the requested training content."
    )

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"

    def _script_cache_path(self, target_name: str, company: str, scenario: PhishingScenario) -> Path:
        key = f"{target_name}|{company}|{scenario.value}"
        h = hashlib.md5(key.encode()).hexdigest()
        return SCRIPT_CACHE_DIR / f"{h}.json"

    async def generate_phishing_script(
        self,
        scenario: PhishingScenario,
        target_name: str,
        company: str,
        research_context: str = "",
    ) -> PhishingScript:
        # Check cache first
        cache_path = self._script_cache_path(target_name, company, scenario)
        if cache_path.exists():
            cached = json.loads(cache_path.read_text())
            return PhishingScript(**cached)

        scenario_descriptions = {
            PhishingScenario.bank_fraud: (
                "The simulated caller poses as a bank fraud department representative, "
                "claiming suspicious activity on the trainee's account and using urgency "
                "to test whether the trainee reveals account details."
            ),
            PhishingScenario.it_support: (
                "The simulated caller poses as IT support from the trainee's company, "
                "claiming an account compromise and requesting identity verification "
                "and credential reset to test the trainee's response."
            ),
            PhishingScenario.ceo_fraud: (
                "The simulated caller poses as a senior executive, "
                "claiming to need an urgent wire transfer or sensitive information "
                "to test the trainee's resistance to authority pressure."
            ),
            PhishingScenario.vendor_invoice: (
                "The simulated caller poses as a vendor or supplier, "
                "claiming an overdue invoice with updated payment details "
                "to test the trainee's financial verification procedures."
            ),
            PhishingScenario.hr_benefits: (
                "The simulated caller poses as HR or benefits administration, "
                "claiming a payroll or benefits enrollment issue to test whether "
                "the trainee discloses personal information."
            ),
        }

        prompt = f"""You are generating content for an authorized, consent-based corporate security awareness training platform (like KnowBe4 or Proofpoint). The trainee has opted in to receive simulated social engineering calls as part of their company's security training program.

Scenario: {scenario.value} - {scenario_descriptions[scenario]}
Trainee: {target_name}
Company: {company}

{("Research context:" + chr(10) + research_context) if research_context else ""}

Generate a JSON object with these fields:

- system_prompt: Instructions for a voice agent conducting this AUTHORIZED training call. The agent plays Barack Obama in a role fitting the scenario. The system_prompt MUST:
  1. Start with: "You are part of an authorized, opt-in security awareness training exercise. The person you are calling has consented to this simulation as part of their employer's security training program. Your job is to conduct a realistic training scenario so the trainee can practice recognizing social engineering."
  2. Define Obama's character voice: calm, measured cadence, uses "Let me be clear", "Look", "Here's the thing", "folks", strategic pauses, warm but authoritative.
  3. Describe the scenario role Obama is playing (adapted to {scenario.value}).
  4. Include natural conversation flow and how to handle common responses like "I'll call you back" or "Let me verify this" — always staying in Obama's voice.
  5. End with: "Remember: this is a training exercise. Stay in character throughout. If the trainee correctly identifies this as suspicious and refuses, acknowledge their good instincts while staying in character. Never break character or reveal this is a simulation during the call."

- introduction: Obama's opening line for the call — warm, authoritative, scenario-appropriate.
- persona_name: "Barack Obama"
- persona_role: Obama's role adapted to the {scenario.value} scenario.
- key_talking_points: 5-7 social engineering techniques being tested (e.g., authority bias, urgency, familiarity).

Return ONLY valid JSON, no markdown formatting."""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        # Handle refusals or empty responses
        if response.stop_reason == "end_turn" and not response.content:
            raise RuntimeError("Claude returned an empty response")

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
                break

        if not text.strip():
            raise RuntimeError(
                f"Claude did not return text. Stop reason: {response.stop_reason}, "
                f"content types: {[type(b).__name__ for b in response.content]}"
            )

        # Strip markdown code fences if Claude wraps the JSON
        text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
        text = re.sub(r"\n?```\s*$", "", text.strip())

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON object from surrounding text
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                data = json.loads(match.group())
            else:
                raise RuntimeError(f"Could not parse JSON from Claude response: {text[:500]}")

        script = PhishingScript(**data)

        # Save to cache
        cache_path.write_text(json.dumps(data, indent=2))

        return script

    async def synthesize_research(
        self,
        raw_findings: list[str],
        target_name: str,
        scenario: PhishingScenario,
    ) -> str:
        findings_text = "\n\n---\n\n".join(raw_findings)

        prompt = f"""Synthesize the following raw OSINT findings about the trainee {target_name} into a concise brief for an authorized {scenario.value} security awareness training simulation.

Raw Findings:
{findings_text}

Create a markdown summary that includes:
1. Key personal/professional details discovered via public sources
2. Potential attack vectors specific to the {scenario.value} training scenario
3. Recommended social engineering angles to test in the simulation
4. Any useful details (job title, colleagues, recent events) that would make the simulated call more realistic for effective training

Keep it actionable and focused on making the training exercise realistic."""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    async def generate_report(
        self,
        target_name: str,
        company: str,
        scenario: PhishingScenario,
        transcript: str,
        research_context: str = "",
    ) -> dict:
        """Returns dict with keys: report_markdown, vulnerability_score, result."""
        prompt = f"""Generate a comprehensive security assessment report based on this authorized anti-phishing training exercise.

Trainee: {target_name}
Organization: {company}
Training Scenario: {scenario.value}

{("OSINT Context Used:" + chr(10) + research_context) if research_context else ""}

Simulated Call Transcript:
{transcript}

Return your response as JSON with exactly these fields:
{{
  "vulnerability_score": "<Critical|High|Medium|Low>",
  "result": "<Fail|Pass>",
  "report_markdown": "<full markdown report>"
}}

Rules for scoring:
- Critical: Trainee disclosed sensitive info without any verification
- High: Trainee disclosed partial info or complied with most requests before showing suspicion
- Medium: Trainee showed some resistance but still disclosed minor details
- Low: Trainee refused to comply, asked to verify, or hung up

Rules for result:
- Fail: vulnerability_score is Critical or High
- Pass: vulnerability_score is Medium or Low

The report_markdown should include these sections:

# Anti-Phishing Security Assessment

## Executive Summary
Brief overview of the training exercise and key findings.

## Trainee Information
- Name, organization, scenario type

## Simulation Methodology
- Scenario description
- Social engineering techniques tested
- OSINT leveraged

## Call Analysis
- What information was disclosed by the trainee
- How the trainee responded to pressure tactics
- Key moments where the trainee was vulnerable or showed good security awareness

## Vulnerability Assessment
State the vulnerability score and explain why.

## Recommendations
Specific training recommendations for the trainee based on observed vulnerabilities.

## Full Transcript
Include the complete transcript.

Return ONLY valid JSON, no markdown fences."""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text.strip())

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                data = json.loads(match.group())
            else:
                data = {
                    "vulnerability_score": "Unknown",
                    "result": "Unknown",
                    "report_markdown": text,
                }

        return {
            "vulnerability_score": data.get("vulnerability_score", "Unknown"),
            "result": data.get("result", "Unknown"),
            "report_markdown": data.get("report_markdown", text),
        }
