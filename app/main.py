from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routers import dashboard, calls, research, reports
from app.services.llm import LLMService
from app.services.cartesia_client import CartesiaClientService
from app.services.researcher import ResearcherService
from app.services.notion_writer import NotionWriterService

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm = LLMService()
    app.state.cartesia = CartesiaClientService()
    app.state.researcher = ResearcherService()
    app.state.notion = NotionWriterService()
    yield


app = FastAPI(title="Obama Cares - Anti-Phishing Security Training", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(dashboard.router)
app.include_router(calls.router)
app.include_router(research.router)
app.include_router(reports.router)
