from fastapi import APIRouter
from .endpoints import freezers, samples, containers, admin  # Add admin import

api_router = APIRouter()
api_router.include_router(freezers.router, prefix="/freezers", tags=["freezers"])
api_router.include_router(samples.router, prefix="/samples", tags=["samples"])
api_router.include_router(containers.router, prefix="/containers", tags=["containers"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])  # Add admin router