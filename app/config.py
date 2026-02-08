from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    cartesia_api_key: str = ""
    cartesia_agent_id: str = ""
    anthropic_api_key: str = ""
    browserbase_api_key: str = ""
    browserbase_project_id: str = ""
    notion_secret: str = ""
    notion_parent_page_id: str = ""
    dashboard_base_url: str = "http://localhost:8000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
