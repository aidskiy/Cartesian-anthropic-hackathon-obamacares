import logging

from exa_py import AsyncExa

from app.config import settings
from app.models.schemas import PhishingScenario, ResearchResult
from app.services.research_cache import ResearchCacheService

logger = logging.getLogger(__name__)


class ResearcherService:
    def __init__(self, cache: ResearchCacheService | None = None):
        self.exa = AsyncExa(api_key=settings.exa_api_key)
        self.cache = cache or ResearchCacheService()

    def _build_search_queries(
        self, name: str, company: str, scenario: PhishingScenario
    ) -> list[str]:
        return [
            f"{name} {company} LinkedIn",
            f"{name} {company}",
        ]

    async def research_target(
        self,
        target_name: str,
        company: str,
        scenario: PhishingScenario,
        additional_queries: list[str] | None = None,
    ) -> ResearchResult:
        # Check cache first
        cached = self.cache.get(target_name, company, scenario)
        if cached:
            logger.info("Using cached research for %s/%s", target_name, company)
            return cached

        queries = self._build_search_queries(target_name, company, scenario)
        if additional_queries:
            queries.extend(additional_queries)

        raw_findings: list[str] = []

        for query in queries:
            try:
                results = await self.exa.search(
                    query,
                    type="auto",
                    num_results=5,
                    contents={"text": {"max_characters": 1000}},
                )
                snippets = []
                for r in results.results:
                    text = (r.text or "").strip()
                    if text:
                        title = r.title or r.url
                        snippets.append(f"[{title}]\n{text}")

                if snippets:
                    finding = f"Query: {query}\n\n" + "\n\n".join(snippets)
                    raw_findings.append(finding)
            except Exception as e:
                logger.warning("Exa search failed for query '%s': %s", query, e)
                raw_findings.append(f"Query: {query}\nError: {str(e)}")

        result = ResearchResult(
            target_name=target_name,
            company=company,
            scenario=scenario,
            raw_findings=raw_findings,
            queries_run=queries,
        )

        # Cache the result for future calls
        self.cache.put(result)

        return result
