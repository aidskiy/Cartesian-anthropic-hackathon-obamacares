import asyncio
import re

from notion_client import Client

from app.config import settings


class NotionWriterService:
    def __init__(self):
        self.client = Client(auth=settings.notion_secret)
        self.parent_page_id = self._extract_id(settings.notion_parent_page_id)
        self.database_id = self._extract_id(settings.notion_database_id)

    @staticmethod
    def _extract_id(value: str) -> str:
        """Extract a Notion UUID from a raw ID or full URL."""
        if not value:
            return ""
        match = re.search(r"([a-f0-9]{32})", value.replace("-", ""))
        if match:
            h = match.group(1)
            return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"
        return value

    def _parse_inline(self, text: str) -> list[dict]:
        """Parse inline markdown (bold, italic, code) into Notion rich_text objects."""
        rich_text = []
        pattern = re.compile(
            r"(\*\*\*(.+?)\*\*\*)"   # bold+italic
            r"|(\*\*(.+?)\*\*)"       # bold
            r"|(\*(.+?)\*)"           # italic
            r"|(`(.+?)`)"             # inline code
        )
        pos = 0
        for m in pattern.finditer(text):
            # Add plain text before this match
            if m.start() > pos:
                plain = text[pos:m.start()]
                if plain:
                    rich_text.extend(self._chunk_text(plain, {}))
            # Determine which group matched
            if m.group(2):  # bold+italic
                rich_text.extend(self._chunk_text(m.group(2), {"bold": True, "italic": True}))
            elif m.group(4):  # bold
                rich_text.extend(self._chunk_text(m.group(4), {"bold": True}))
            elif m.group(6):  # italic
                rich_text.extend(self._chunk_text(m.group(6), {"italic": True}))
            elif m.group(8):  # code
                rich_text.extend(self._chunk_text(m.group(8), {"code": True}))
            pos = m.end()
        # Trailing text
        if pos < len(text):
            rich_text.extend(self._chunk_text(text[pos:], {}))
        if not rich_text:
            rich_text = [{"type": "text", "text": {"content": ""}}]
        return rich_text

    def _chunk_text(self, text: str, annotations: dict) -> list[dict]:
        """Split text into 2000-char chunks with annotations."""
        chunks = []
        for i in range(0, max(len(text), 1), 2000):
            chunk = text[i:i + 2000]
            item = {"type": "text", "text": {"content": chunk}}
            if annotations:
                item["annotations"] = annotations
            chunks.append(item)
        return chunks

    def _markdown_to_blocks(self, markdown: str) -> list[dict]:
        """Convert a markdown string into a list of Notion block objects."""
        blocks = []
        lines = markdown.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # Code block (fenced)
            if line.strip().startswith("```"):
                lang = line.strip().lstrip("`").strip()
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # skip closing ```
                code_text = "\n".join(code_lines)
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": self._chunk_text(code_text, {}),
                        "language": lang or "plain text",
                    },
                })
                continue

            # Empty line — skip
            if not line.strip():
                i += 1
                continue

            # Headings
            if line.startswith("### "):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": self._parse_inline(line[4:].strip())},
                })
            elif line.startswith("## "):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": self._parse_inline(line[3:].strip())},
                })
            elif line.startswith("# "):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {"rich_text": self._parse_inline(line[2:].strip())},
                })

            # Horizontal rule
            elif line.strip() in ("---", "***", "___"):
                blocks.append({"object": "block", "type": "divider", "divider": {}})

            # Bulleted list
            elif re.match(r"^[\-\*]\s", line.strip()):
                content = re.sub(r"^[\-\*]\s+", "", line.strip())
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": self._parse_inline(content)},
                })

            # Numbered list
            elif re.match(r"^\d+\.\s", line.strip()):
                content = re.sub(r"^\d+\.\s+", "", line.strip())
                blocks.append({
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {"rich_text": self._parse_inline(content)},
                })

            # Blockquote
            elif line.strip().startswith("> "):
                content = line.strip()[2:]
                blocks.append({
                    "object": "block",
                    "type": "quote",
                    "quote": {"rich_text": self._parse_inline(content)},
                })

            # Regular paragraph — collect consecutive non-empty, non-special lines
            else:
                para_lines = [line.strip()]
                while (i + 1 < len(lines)
                       and lines[i + 1].strip()
                       and not lines[i + 1].startswith("#")
                       and not lines[i + 1].strip().startswith("```")
                       and not re.match(r"^[\-\*]\s", lines[i + 1].strip())
                       and not re.match(r"^\d+\.\s", lines[i + 1].strip())
                       and not lines[i + 1].strip().startswith("> ")
                       and lines[i + 1].strip() not in ("---", "***", "___")):
                    i += 1
                    para_lines.append(lines[i].strip())
                content = " ".join(para_lines)
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": self._parse_inline(content)},
                })

            i += 1

        return blocks

    async def ensure_database(self) -> str:
        """Create the assessments database under the parent page if needed."""
        import httpx

        # Validate existing database_id if set
        if self.database_id:
            def _check():
                resp = httpx.get(
                    f"https://api.notion.com/v1/databases/{self.database_id}",
                    headers={
                        "Authorization": f"Bearer {settings.notion_secret}",
                        "Notion-Version": "2022-06-28",
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if not data.get("archived", False) and data.get("properties"):
                        return True
                return False

            valid = await asyncio.to_thread(_check)
            if valid:
                return self.database_id
            self.database_id = ""

        # Use raw HTTP because notion-client 2.7.0 silently drops properties

        def _create_db():
            resp = httpx.post(
                "https://api.notion.com/v1/databases",
                headers={
                    "Authorization": f"Bearer {settings.notion_secret}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                },
                json={
                    "parent": {"type": "page_id", "page_id": self.parent_page_id},
                    "title": [{"type": "text", "text": {"content": "Phishing Assessments"}}],
                    "properties": {
                        "Name": {"title": {}},
                        "Date": {"date": {}},
                        "Target": {"rich_text": {}},
                        "Company": {"rich_text": {}},
                        "Scenario": {
                            "select": {
                                "options": [
                                    {"name": "bank_fraud", "color": "red"},
                                    {"name": "it_support", "color": "blue"},
                                    {"name": "ceo_fraud", "color": "purple"},
                                    {"name": "vendor_invoice", "color": "orange"},
                                    {"name": "hr_benefits", "color": "green"},
                                ]
                            }
                        },
                        "Vulnerability": {
                            "select": {
                                "options": [
                                    {"name": "Critical", "color": "red"},
                                    {"name": "High", "color": "orange"},
                                    {"name": "Medium", "color": "yellow"},
                                    {"name": "Low", "color": "green"},
                                ]
                            }
                        },
                        "Result": {
                            "select": {
                                "options": [
                                    {"name": "Fail", "color": "red"},
                                    {"name": "Pass", "color": "green"},
                                ]
                            }
                        },
                    },
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

        db = await asyncio.to_thread(_create_db)
        self.database_id = db["id"]
        return self.database_id

    async def create_call_report(
        self,
        title: str,
        target_name: str,
        company: str,
        scenario: str,
        research_context: str,
        transcript: str,
        report_markdown: str,
        vulnerability_score: str = "Unknown",
        result: str = "Unknown",
    ) -> str:
        """Create a database row with properties and the full report as page content."""
        from datetime import datetime, timezone

        db_id = await self.ensure_database()

        # Build page content blocks
        children: list[dict] = []

        # Assessment report
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": self._parse_inline("Assessment Report")},
        })
        if report_markdown:
            children.extend(self._markdown_to_blocks(report_markdown))
        children.append({"object": "block", "type": "divider", "divider": {}})

        # Research context
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": self._parse_inline("Research Context")},
        })
        if research_context:
            children.extend(self._markdown_to_blocks(research_context))
        else:
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": "No research conducted."}}]},
            })
        children.append({"object": "block", "type": "divider", "divider": {}})

        # Full transcript
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": self._parse_inline("Full Transcript")},
        })
        if transcript:
            children.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": self._chunk_text(transcript, {}),
                    "language": "plain text",
                },
            })
        else:
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": "No transcript available."}}]},
            })

        # Database row properties
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        valid_scores = ("Critical", "High", "Medium", "Low")
        valid_results = ("Fail", "Pass")
        vuln_select = vulnerability_score if vulnerability_score in valid_scores else "Medium"
        result_select = result if result in valid_results else "Fail"

        properties = {
            "Name": {"title": [{"type": "text", "text": {"content": title}}]},
            "Date": {"date": {"start": today}},
            "Target": {"rich_text": [{"type": "text", "text": {"content": target_name}}]},
            "Company": {"rich_text": [{"type": "text", "text": {"content": company}}]},
            "Scenario": {"select": {"name": scenario}},
            "Vulnerability": {"select": {"name": vuln_select}},
            "Result": {"select": {"name": result_select}},
        }

        first_batch = children[:100]
        remaining = children[100:]

        # Use raw HTTP with pinned Notion-Version (SDK uses incompatible version)
        import httpx

        def _create():
            resp = httpx.post(
                "https://api.notion.com/v1/pages",
                headers={
                    "Authorization": f"Bearer {settings.notion_secret}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                },
                json={
                    "parent": {"database_id": db_id},
                    "properties": properties,
                    "children": first_batch,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

        page = await asyncio.to_thread(_create)
        page_id = page["id"]

        for batch_start in range(0, len(remaining), 100):
            batch = remaining[batch_start:batch_start + 100]

            def _append(b=batch):
                resp = httpx.patch(
                    f"https://api.notion.com/v1/blocks/{page_id}/children",
                    headers={
                        "Authorization": f"Bearer {settings.notion_secret}",
                        "Notion-Version": "2022-06-28",
                        "Content-Type": "application/json",
                    },
                    json={"children": b},
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.json()

            await asyncio.to_thread(_append)

        return page.get("url", "")
