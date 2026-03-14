from datetime import datetime
from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        app=settings.app_name,
        env=settings.app_env,
        version="0.1.0",
    )


@router.get("/api/v1/meta", tags=["system"])
def meta():
    return {
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "server_time": datetime.utcnow().isoformat() + "Z",
        "modules": {
            "faturas": "planned",
            "boletos": "planned",
            "dashboard": "planned",
            "historico": "planned",
            "integrations": {
                "bigquery": "planned",
                "sicoob": "planned",
            },
        },
    }


@router.get("/api/v1/faturas", tags=["faturas"])
def list_faturas():
    return {
        "items": [],
        "total": 0,
        "message": "Endpoint base criado. Integracao com workflow_adapter vira na proxima etapa."
    }


@router.get("/api/v1/boletos", tags=["boletos"])
def list_boletos():
    return {
        "items": [],
        "total": 0,
        "message": "Endpoint base criado. Integracao com calc_engine e emissao Sicoob vira na proxima etapa."
    }


@router.get("/api/v1/dashboard/resumo", tags=["dashboard"])
def dashboard_resumo():
    return {
        "cards": [],
        "series": [],
        "message": "Endpoint base criado. Integracao com reporting_dataset vira na proxima etapa."
    }


@router.get("/api/v1/historico", tags=["historico"])
def historico():
    return {
        "items": [],
        "message": "Endpoint base criado. Historico real vira na proxima etapa."
    }