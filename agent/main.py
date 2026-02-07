"""Obama Cares Voice Agent — Cartesia Line SDK entry point.

This agent handles live phishing training calls using Claude as the LLM brain.
It receives system prompts and context from the dashboard via call metadata.
"""

import os

import httpx
from cartesia_line import VoiceAgentApp, LlmAgent

from tools import lookup_account, verify_identity

app = VoiceAgentApp()

DASHBOARD_BASE_URL = os.environ.get("DASHBOARD_BASE_URL", "http://localhost:8000")


@app.agent
def get_agent(env, call_request):
    """Factory that creates an LLM agent for each inbound/outbound call.

    Extracts the phishing script from call metadata and configures Claude
    as the conversation engine.
    """
    metadata = call_request.get("metadata", {})
    system_prompt = metadata.get("system_prompt", "You are a helpful assistant.")
    introduction = metadata.get("introduction", "Hello, how can I help you?")
    call_id = metadata.get("dashboard_call_id", "")

    tools = [
        {
            "name": "lookup_account",
            "description": (
                "Look up a bank account to add realism to the call. "
                "Use this when the target provides account details."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number provided by the target",
                    },
                    "last_four_ssn": {
                        "type": "string",
                        "description": "Last four SSN digits if provided",
                    },
                },
            },
            "function": lookup_account,
        },
        {
            "name": "verify_identity",
            "description": (
                "Record identity information the target reveals during the call. "
                "Call this whenever the target shares PII like SSN, DOB, address, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "enum": ["ssn", "dob", "address", "account_number", "password", "email"],
                        "description": "Type of PII revealed",
                    },
                    "info_value": {
                        "type": "string",
                        "description": "The actual value the target provided",
                    },
                },
            },
            "function": verify_identity,
        },
        {
            "name": "get_call_context",
            "description": (
                "Fetch additional research context from the dashboard. "
                "Use this if you need more background on the target mid-call."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "call_id": {
                        "type": "string",
                        "description": "The dashboard call ID",
                    },
                },
            },
            "function": lambda call_id=call_id: _fetch_context(call_id),
        },
    ]

    agent = LlmAgent(
        model="anthropic/claude-sonnet-4-5",
        system_prompt=system_prompt,
        introduction=introduction,
        tools=tools,
    )

    return agent


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
