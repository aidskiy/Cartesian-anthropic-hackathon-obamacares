from notion_client import Client

from app.config import settings


class NotionWriterService:
    def __init__(self):
        self.client = Client(auth=settings.notion_secret)
        self.parent_page_id = settings.notion_parent_page_id

    def _heading(self, level: int, text: str) -> dict:
        key = f"heading_{level}"
        return {
            "object": "block",
            "type": key,
            key: {
                "rich_text": [{"type": "text", "text": {"content": text}}],
            },
        }

    def _paragraph(self, text: str) -> dict:
        # Notion blocks have a 2000-char limit per rich_text item
        chunks = [text[i : i + 2000] for i in range(0, len(text), 2000)]
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": chunk}} for chunk in chunks
                ],
            },
        }

    def _divider(self) -> dict:
        return {"object": "block", "type": "divider", "divider": {}}

    async def create_call_report(
        self,
        title: str,
        target_name: str,
        company: str,
        scenario: str,
        research_context: str,
        transcript: str,
        report_markdown: str,
    ) -> str:
        """Create a Notion page with the call report. Returns the page URL."""
        children = [
            self._heading(2, "Target Information"),
            self._paragraph(f"Name: {target_name}\nCompany: {company}\nScenario: {scenario}"),
            self._divider(),
            self._heading(2, "Research Context"),
            self._paragraph(research_context or "No research conducted."),
            self._divider(),
            self._heading(2, "Assessment Report"),
            self._paragraph(report_markdown),
            self._divider(),
            self._heading(2, "Full Transcript"),
            self._paragraph(transcript or "No transcript available."),
        ]

        page = self.client.pages.create(
            parent={"page_id": self.parent_page_id},
            properties={
                "title": [{"type": "text", "text": {"content": title}}],
            },
            children=children,
        )

        return page.get("url", "")
