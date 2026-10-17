from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    appointments,
    auth,
    cash,
    clients,
    employees,
    reports,
    sales,
    services,
    users,
)
from app.core.config import settings

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")
for module in (auth, users, clients, services, employees, appointments, sales, cash, reports):
    api.include_router(module.router)


@api.get("/config", tags=["Sistema"])
def public_config():
    """Datos que necesita la interfaz web antes de iniciar sesión."""
    return {
        "app_name": settings.app_name,
        "timezone": settings.timezone,
        "currency_symbol": settings.currency_symbol,
        "slot_minutes": settings.slot_minutes,
    }


app.include_router(api)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def web_app():
    return FileResponse(STATIC_DIR / "index.html")
