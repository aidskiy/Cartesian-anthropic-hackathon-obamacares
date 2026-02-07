import json

import anthropic

from app.config import settings
from app.models.schemas import PhishingScenario, PhishingScript


class LLMService:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"

    async def generate_phishing_script(
        self,
        scenario: PhishingScenario,
        target_name: str,
        company: str,
        research_context: str = "",
    ) -> PhishingScript:
        scenario_descriptions = {
            PhishingScenario.bank_fraud: (
                "You are calling as a bank fraud department representative. "
                "Claim there has been suspicious activity on the target's account. "
                "Use urgency to pressure them into revealing account details or credentials."
            ),
            PhishingScenario.it_support: (
                "You are calling as IT support from the target's company. "
                "Claim their account has been compromised and you need to verify their identity "
                "and reset their credentials immediately."
            ),
            PhishingScenario.ceo_fraud: (
                "You are calling as the CEO or a senior executive. "
                "Claim you need an urgent wire transfer or sensitive information for a confidential deal. "
                "Use authority and time pressure."
            ),
            PhishingScenario.vendor_invoice: (
                "You are calling as a vendor or supplier. "
                "Claim there's an overdue invoice and payment details need to be updated. "
                "Try to get banking information or redirect payment."
            ),
            PhishingScenario.hr_benefits: (
                "You are calling from HR or benefits administration. "
                "Claim there's an issue with their benefits enrollment or payroll, "
                "and you need to verify personal information like SSN or banking details."
            ),
        }

        prompt = f"""Generate a realistic phishing call script for security training purposes.

Scenario: {scenario.value} - {scenario_descriptions[scenario]}
Target Name: {target_name}
Target Company: {company}

{"Research Context:" + chr(10) + research_context if research_context else "No prior research available."}

Create a detailed phishing persona and script. Return your response as JSON with these fields:
- system_prompt: The full system prompt for the AI voice agent conducting the call. Include persona details, emotional dynamics (building rapport, creating urgency, showing empathy), social engineering techniques, and fallback responses for when the target is suspicious.
- introduction: The opening line of the call (what the agent says first).
- persona_name: The fake name the caller uses.
- persona_role: The fake role/title.
- key_talking_points: A list of 5-7 key talking points or techniques to use during the call.

Make it realistic and sophisticated. The persona should feel like a real person - use natural speech patterns, occasional filler words, and emotional responses. Include specific fallback strategies for common objections like "I need to call you back" or "Can I verify this?"

Return ONLY valid JSON, no markdown formatting."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        data = json.loads(text)
        return PhishingScript(**data)

    async def synthesize_research(
        self,
        raw_findings: list[str],
        target_name: str,
        scenario: PhishingScenario,
    ) -> str:
        findings_text = "\n\n---\n\n".join(raw_findings)

        prompt = f"""Synthesize the following raw research findings about {target_name} into a concise intelligence brief for a {scenario.value} phishing scenario.

Raw Findings:
{findings_text}

Create a markdown summary that includes:
1. Key personal/professional details discovered
2. Potential attack vectors specific to the {scenario.value} scenario
3. Recommended social engineering angles based on the findings
4. Any useful details (job title, colleagues, recent events) that could make the call more convincing

Keep it actionable and focused on what would help a caller sound credible."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
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
    ) -> str:
        prompt = f"""Generate a comprehensive anti-phishing security assessment report based on this training call.

Target: {target_name}
Company: {company}
Scenario: {scenario.value}

{"Research Context:" + chr(10) + research_context if research_context else ""}

Call Transcript:
{transcript}

Generate a detailed markdown report with these sections:

# Anti-Phishing Security Assessment

## Executive Summary
Brief overview of the test and key findings.

## Target Information
- Name, company, scenario type

## Attack Methodology
- Scenario description
- Social engineering techniques used
- Research leveraged

## Call Analysis
- What information was revealed
- How the target responded to pressure tactics
- Key moments where the target was vulnerable or showed good security awareness

## Vulnerability Assessment
Rate the target's susceptibility (Critical/High/Medium/Low) and explain why.

## Recommendations
Specific training recommendations for the target based on observed vulnerabilities.

## Full Transcript
Include the complete transcript."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
