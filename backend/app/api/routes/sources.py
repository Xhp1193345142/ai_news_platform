from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.content import SourceResponse
from app.services.content import list_sources

router = APIRouter(prefix="/sources")


@router.get("", response_model=list[SourceResponse])
async def sources_index(session: DbSession, _: CurrentUser) -> list[SourceResponse]:
    return [SourceResponse.model_validate(source) for source in await list_sources(session)]
