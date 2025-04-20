from fastapi import APIRouter
from .endpoints import freezers, samples, containers  # Make sure to import containers

api_router = APIRouter()
api_router.include_router(freezers.router, prefix="/freezers", tags=["freezers"])
api_router.include_router(samples.router, prefix="/samples", tags=["samples"])
api_router.include_router(containers.router, prefix="/containers", tags=["containers"])  # Add this line