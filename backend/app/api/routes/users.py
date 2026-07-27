from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.auth import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def read_current_user(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
