"""Application composition; HTTP responsibilities live in app.api modules."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .storage import init
from .api import media, counting, analysis, results, reports, evaluation
STATIC = Path(__file__).resolve().parents[1] / "static"
@asynccontextmanager
async def lifespan(_app):
    init()
    yield


app = FastAPI(
    title="InnovaTransport API",
    version="2.0.0",
    description=(
        "Компактный API для загрузки видео, запуска локального анализа "
        "и просмотра результатов. Интерактивная Swagger-документация доступна "
        "по адресу `/docs`."
    ),
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "Система", "description": "Проверка готовности сервиса."},
        {"name": "Видео", "description": "Загрузка, каталог и медиаданные."},
        {"name": "Зоны", "description": "Зоны и линии подсчёта."},
        {"name": "Анализ", "description": "Запуск, статус и управление анализом."},
        {"name": "Результаты", "description": "Сводка, события, картограмма и экспорт."},
    ],
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health", tags=["Система"], summary="Проверить готовность API")
def health():
    from .runtime import runtime_settings
    return {"ok": True, "runtime": runtime_settings()}



for module in (media, counting, analysis, results, reports, evaluation):
    app.include_router(module.app)
