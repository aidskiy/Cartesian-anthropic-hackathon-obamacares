import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta

from app.models.schemas import ResearchResult, PhishingScenario

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".research_cache"


class ResearchCacheService:
    def __init__(self, cache_dir: Path = CACHE_DIR, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl = timedelta(hours=ttl_hours)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, target_name: str, company: str, scenario: str) -> str:
        raw = f"{target_name.lower().strip()}:{company.lower().strip()}:{scenario}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(
        self, target_name: str, company: str, scenario: PhishingScenario
    ) -> ResearchResult | None:
        key = self._cache_key(target_name, company, scenario.value)
        path = self._cache_path(key)

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            cached_at = datetime.fromisoformat(data.get("cached_at", ""))
            if datetime.utcnow() - cached_at > self.ttl:
                logger.info("Cache expired for %s/%s/%s", target_name, company, scenario.value)
                path.unlink(missing_ok=True)
                return None

            logger.info("Cache hit for %s/%s/%s", target_name, company, scenario.value)
            return ResearchResult(**data["result"])
        except Exception as e:
            logger.warning("Failed to read cache: %s", e)
            return None

    def put(self, result: ResearchResult) -> None:
        key = self._cache_key(
            result.target_name, result.company, result.scenario.value
        )
        path = self._cache_path(key)

        data = {
            "cached_at": datetime.utcnow().isoformat(),
            "result": result.model_dump(mode="json"),
        }

        try:
            path.write_text(json.dumps(data, indent=2))
            logger.info(
                "Cached research for %s/%s/%s",
                result.target_name,
                result.company,
                result.scenario.value,
            )
        except Exception as e:
            logger.warning("Failed to write cache: %s", e)

    def clear(self) -> int:
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count
