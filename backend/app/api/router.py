from fastapi import APIRouter

from app.api.routes import articles, auth, health, media, sources, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(articles.router, tags=["articles"])
api_router.include_router(sources.router, tags=["sources"])
api_router.include_router(media.router, tags=["media"])
