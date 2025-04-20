from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class ContainerAllocationRequest(BaseModel):
    """Request to allocate space for multiple containers."""
    container_type_id: int
    number_of_containers: int = Field(..., gt=0)
    sample_type: Literal["study_sample", "nonglp_preparation", "glp_preparation"]
    project_id: Optional[str] = None

class DrawerAllocation(BaseModel):
    """Information about drawer allocation for containers."""
    drawer_id: int
    freezer_asset_id: str
    layer_number: int
    rack_number: int
    drawer_number: int
    drawer_coordinate: str
    container_count: int