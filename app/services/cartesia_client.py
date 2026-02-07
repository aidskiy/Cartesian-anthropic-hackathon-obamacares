import asyncio
import logging

import httpx

from app.config import settings

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
logger = logging.getLogger(__name__)


class CartesiaClientService:
    def __init__(self):
        self.api_key = settings.cartesia_api_key
        self.agent_id = settings.cartesia_agent_id
        self.base_url = "https://api.cartesia.ai"
        self.headers = {
            "X-API-Key": self.api_key,
            "Cartesia-Version": "2025-04-16",
            "Content-Type": "application/json",
        }

    async def list_phone_numbers(self) -> list[dict]:
        """GET /agents/{agent_id}/phone-numbers"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/agents/{self.agent_id}/phone-numbers",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def update_agent(self, system_prompt: str, first_message: str) -> dict:
        """PATCH /agents/{agent_id} — update the agent config before a call."""
        payload = {
            "llm": {"system_prompt": system_prompt},
            "first_message": first_message,
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.patch(
                f"{self.base_url}/agents/{self.agent_id}",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def initiate_call(
        self,
        to_number: str,
        from_number: str,
        system_prompt: str,
        introduction: str,
        context_metadata: dict | None = None,
    ) -> dict:
        """Initiate an outbound call.

        1. Update the agent config with the new system prompt / introduction.
        2. Use the `cartesia` CLI to place the call (no REST create-call endpoint exists).
        3. Return a dict with the call info.
        """
        # Update agent with the script for this call
        await self.update_agent(system_prompt, introduction)

        # Kick off the call via CLI in a background subprocess
        proc = await asyncio.create_subprocess_exec(
            "cartesia", "call", to_number,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info("Started cartesia call to %s (pid=%s)", to_number, proc.pid)

        # Give Cartesia a moment to register the call, then find it via the API
        await asyncio.sleep(3)

        # Try to find the most recent call for this agent
        calls = await self.list_calls(limit=1)
        call_data = calls[0] if calls else {}
        call_id = call_data.get("id", f"cli-{proc.pid}")

        return {"id": call_id, "pid": proc.pid, "status": "initiated"}

    async def get_call(self, call_id: str) -> dict:
        """GET /agents/calls/{call_id}"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/agents/calls/{call_id}",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_transcript(self, call_id: str) -> str:
        call_data = await self.get_call(call_id)
        transcript = call_data.get("transcript", [])
        if not transcript:
            return "No transcript available yet."

        lines = []
        for entry in transcript:
            role = entry.get("role", "unknown").title()
            text = entry.get("text", entry.get("content", ""))
            lines.append(f"{role}: {text}")

        return "\n\n".join(lines)

    async def list_calls(self, limit: int = 20) -> list[dict]:
        """GET /agents/calls?agent_id=..."""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/agents/calls",
                headers=self.headers,
                params={"agent_id": self.agent_id, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            # API returns {"data": [...]} with pagination
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data
