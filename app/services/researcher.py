from browserbase import Browserbase
from playwright.async_api import async_playwright

from app.config import settings
from app.models.schemas import PhishingScenario, ResearchResult


class ResearcherService:
    def __init__(self):
        self.bb = Browserbase(api_key=settings.browserbase_api_key)
        self.project_id = settings.browserbase_project_id

    def _build_search_queries(
        self, name: str, company: str, scenario: PhishingScenario
    ) -> list[str]:
        base_queries = [
            f"{name} {company} LinkedIn",
            f"{name} {company}",
        ]

        scenario_queries = {
            PhishingScenario.bank_fraud: [
                f"{company} customer service phone number",
                f"{company} fraud department contact",
            ],
            PhishingScenario.it_support: [
                f"{company} IT helpdesk",
                f"{company} technology stack",
            ],
            PhishingScenario.ceo_fraud: [
                f"{company} CEO executive team",
                f"{company} recent acquisitions deals",
            ],
            PhishingScenario.vendor_invoice: [
                f"{company} suppliers vendors partners",
                f"{company} accounts payable contact",
            ],
            PhishingScenario.hr_benefits: [
                f"{company} HR department benefits",
                f"{company} employee benefits provider",
            ],
        }

        return base_queries + scenario_queries.get(scenario, [])

    async def research_target(
        self,
        target_name: str,
        company: str,
        scenario: PhishingScenario,
        additional_queries: list[str] | None = None,
    ) -> ResearchResult:
        queries = self._build_search_queries(target_name, company, scenario)
        if additional_queries:
            queries.extend(additional_queries)

        raw_findings: list[str] = []

        session = self.bb.sessions.create(project_id=self.project_id)
        debug_urls = self.bb.sessions.debug(session.id)
        ws_url = debug_urls.debugger_fullscreen_url

        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(ws_url)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()

            for query in queries:
                try:
                    await page.goto(
                        f"https://www.google.com/search?q={query}", timeout=15000
                    )
                    await page.wait_for_load_state("domcontentloaded")

                    # Extract search result snippets
                    results = await page.query_selector_all("div.g")
                    snippets = []
                    for result in results[:5]:
                        text = await result.inner_text()
                        if text.strip():
                            snippets.append(text.strip())

                    if snippets:
                        finding = f"Query: {query}\n\n" + "\n\n".join(snippets)
                        raw_findings.append(finding)
                except Exception as e:
                    raw_findings.append(f"Query: {query}\nError: {str(e)}")

            await browser.close()

        return ResearchResult(
            target_name=target_name,
            company=company,
            scenario=scenario,
            raw_findings=raw_findings,
            queries_run=queries,
        )
