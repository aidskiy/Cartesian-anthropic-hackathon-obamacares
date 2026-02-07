# Obama Cares - Anti-Phishing Security Training

Automated phishing security assessment platform. Conducts realistic phishing calls using AI voice agents to test employee security awareness.

## Architecture

- **Dashboard** (FastAPI + Jinja2 + HTMX) — control plane for initiating calls, running research, viewing reports
- **Voice Agent** (Cartesia Line SDK + Claude) — handles live phone conversations

## Setup

```bash
cp .env.example .env
# Fill in API keys

pip install -r requirements.txt
playwright install chromium

uvicorn app.main:app --reload
```

## Environment Variables

| Variable | Description |
|---|---|
| `CARTESIA_API_KEY` | Cartesia API key for voice calls |
| `CARTESIA_AGENT_ID` | Deployed Cartesia agent ID |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `BROWSERBASE_API_KEY` | Browserbase API key for research |
| `BROWSERBASE_PROJECT_ID` | Browserbase project ID |
| `NOTION_SECRET` | Notion integration secret |
| `NOTION_PARENT_PAGE_ID` | Notion page to write reports under |

## Deploy

```bash
# Dashboard
fly launch
fly secrets set ANTHROPIC_API_KEY=... CARTESIA_API_KEY=... ...
fly deploy

# Voice Agent
cd agent
cartesia deploy
```
