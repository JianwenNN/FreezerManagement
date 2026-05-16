from fastapi import APIRouter
from .endpoints import freezers, containers, samples, admin

api_router = APIRouter()
api_router.include_router(freezers.router,   prefix="/freezers",   tags=["freezers"])
api_router.include_router(containers.router, prefix="/containers", tags=["containers"])
api_router.include_router(samples.router,    prefix="/samples",    tags=["samples"])
api_router.include_router(admin.router,      prefix="/admin",      tags=["admin"])
