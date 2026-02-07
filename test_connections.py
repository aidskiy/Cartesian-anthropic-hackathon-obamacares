"""Quick smoke test for all external service connections."""

import asyncio
import sys

from app.config import settings


def check_keys():
    """Print which API keys are set."""
    keys = {
        "CARTESIA_API_KEY": settings.cartesia_api_key,
        "CARTESIA_AGENT_ID": settings.cartesia_agent_id,
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
        "BROWSERBASE_API_KEY": settings.browserbase_api_key,
        "BROWSERBASE_PROJECT_ID": settings.browserbase_project_id,
        "NOTION_SECRET": settings.notion_secret,
        "NOTION_PARENT_PAGE_ID": settings.notion_parent_page_id,
    }
    print("=== API Keys ===")
    for name, val in keys.items():
        status = f"set ({val[:8]}...)" if val else "MISSING"
        print(f"  {name}: {status}")
    print()
    return keys


async def test_cartesia():
    """Test Cartesia API — list phone numbers."""
    print("=== Cartesia ===")
    from app.services.cartesia_client import CartesiaClientService
    client = CartesiaClientService()
    try:
        numbers = await client.list_phone_numbers()
        print(f"  OK — {len(numbers)} phone number(s) available")
        for n in numbers:
            print(f"    {n.get('phone_number', n)}")
    except Exception as e:
        print(f"  FAILED — {e}")
    print()


async def test_browserbase():
    """Test Browserbase — create and immediately release a session."""
    print("=== Browserbase ===")
    import asyncio as aio
    from browserbase import Browserbase
    bb = Browserbase(api_key=settings.browserbase_api_key)
    try:
        session = await aio.to_thread(
            bb.sessions.create, project_id=settings.browserbase_project_id
        )
        print(f"  OK — session created: {session.id}")
        debug = await aio.to_thread(bb.sessions.debug, session.id)
        print(f"  OK — ws_url: {debug.ws_url[:60]}...")
        # Clean up
        await aio.to_thread(
            bb.sessions.update, session.id, status="REQUEST_RELEASE"
        )
        print("  OK — session released")
    except Exception as e:
        print(f"  FAILED — {e}")
    print()


async def test_anthropic():
    """Test Anthropic API — send a trivial message."""
    print("=== Anthropic ===")
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        resp = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'connection test OK' and nothing else."}],
        )
        print(f"  OK — {resp.content[0].text}")
    except Exception as e:
        print(f"  FAILED — {e}")
    print()


async def test_notion():
    """Test Notion API — verify we can read the parent page."""
    print("=== Notion ===")
    if not settings.notion_secret or not settings.notion_parent_page_id:
        print("  SKIPPED — keys not set")
        print()
        return
    import asyncio as aio
    from notion_client import Client
    client = Client(auth=settings.notion_secret)
    try:
        page = await aio.to_thread(client.pages.retrieve, settings.notion_parent_page_id)
        title = "untitled"
        props = page.get("properties", {})
        if "title" in props:
            title_arr = props["title"].get("title", [])
            if title_arr:
                title = title_arr[0].get("plain_text", "untitled")
        print(f"  OK — parent page: \"{title}\"")
    except Exception as e:
        print(f"  FAILED — {e}")
    print()


async def main():
    keys = check_keys()

    if keys["CARTESIA_API_KEY"]:
        await test_cartesia()

    if keys["BROWSERBASE_API_KEY"] and keys["BROWSERBASE_PROJECT_ID"]:
        await test_browserbase()

    if keys["ANTHROPIC_API_KEY"]:
        await test_anthropic()

    await test_notion()

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
