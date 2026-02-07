"""Obama Cares Voice Agent — Cartesia Line SDK entry point.

This agent handles live phishing training calls using Claude as the LLM brain.
It receives system prompts and context from the dashboard via call metadata.
"""

import os

import httpx
from line.llm_agent import LlmAgent, LlmConfig
from line.voice_agent_app import VoiceAgentApp, AgentEnv

from tools import lookup_account, verify_identity

DASHBOARD_BASE_URL = os.environ.get("DASHBOARD_BASE_URL", "http://localhost:8000")

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant conducting a phone call."
DEFAULT_INTRODUCTION = "Hello, how can I help you today?"


def _fetch_context(call_id: str) -> str:
    """Synchronously fetch research context from the dashboard API."""
    if not call_id:
        return "No call ID available to fetch context."
    try:
        resp = httpx.get(
            f"{DASHBOARD_BASE_URL}/api/calls/{call_id}/context",
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("context", "No additional context available.")
    except Exception as e:
        return f"Could not fetch context: {str(e)}"


async def get_agent(env: AgentEnv, call_request):
    """Factory that creates an LLM agent for each inbound/outbound call.

    Extracts the phishing script from call metadata and configures Claude
    as the conversation engine.
    """
    metadata = getattr(call_request, "metadata", None) or {}
    system_prompt = metadata.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
    introduction = metadata.get("introduction", DEFAULT_INTRODUCTION)
    call_id = metadata.get("dashboard_call_id", "")

    tools = [lookup_account, verify_identity]

    # If we have a call_id, pre-fetch context and append to system prompt
    if call_id:
        context = _fetch_context(call_id)
        if context and "Could not fetch" not in context:
            system_prompt += f"\n\nResearch context about the target:\n{context}"

    agent = LlmAgent(
        model="anthropic/claude-sonnet-4-5-20250929",
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        tools=tools,
        config=LlmConfig(
            system_prompt=system_prompt,
            introduction=introduction,
        ),
    )

    return agent


app = VoiceAgentApp(get_agent=get_agent)

if __name__ == "__main__":
    app.run()
