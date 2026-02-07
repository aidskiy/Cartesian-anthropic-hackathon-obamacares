import httpx

from app.config import settings

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


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
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/phone-numbers",
                headers=self.headers,
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
        """Initiate an outbound call via the Cartesia API."""
        payload = {
            "agent_id": self.agent_id,
            "to": to_number,
            "from": from_number,
            "agent_config_override": {
                "llm": {
                    "system_prompt": system_prompt,
                },
                "first_message": introduction,
            },
        }
        if context_metadata:
            payload["metadata"] = context_metadata

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/calls",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_call(self, call_id: str) -> dict:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/calls/{call_id}",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_transcript(self, call_id: str) -> str:
        call_data = await self.get_call(call_id)
        messages = call_data.get("messages", [])
        if not messages:
            return "No transcript available yet."

        lines = []
        for msg in messages:
            role = msg.get("role", "unknown").title()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")

        return "\n\n".join(lines)

    async def list_calls(self, limit: int = 20) -> list[dict]:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/calls",
                headers=self.headers,
                params={"limit": limit},
            )
            resp.raise_for_status()
            return resp.json()
