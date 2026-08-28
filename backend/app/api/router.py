"""
Central API router — registers all endpoint routers.
"""
from fastapi import APIRouter
from app.api.endpoints import upload, status, compile

api_router = APIRouter()

api_router.include_router(upload.router, tags=["Upload"])
api_router.include_router(status.router, tags=["Status"])
api_router.include_router(compile.router, tags=["Compile"])
