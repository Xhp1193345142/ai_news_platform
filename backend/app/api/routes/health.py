from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health", summary="API health probe")
async def healthcheck() -> dict[str, str]:
    """A dependency-free probe used by local orchestration and deployment checks."""
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}
