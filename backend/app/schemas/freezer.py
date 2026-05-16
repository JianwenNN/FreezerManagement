from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class FreezerCreateRequest(BaseModel):
    """
    Payload for registering a new freezer.

    study_sample_capacity and stdqc_capacity define how many containers
    of each type fit in ONE drawer of this freezer. These are fixed by
    the physical drawer dimensions and apply uniformly to all drawers.

    A drawer starts typeless. The first container placed in it locks the
    drawer to that sample type. An empty drawer is flexible again.

    The system auto-generates the full structure (layers → racks → drawers)
    from the dimension fields.
    """
    asset_id:               str           = Field(..., max_length=50)
    temperature:            float
    num_of_layers:          int           = Field(..., gt=0)
    num_of_rack_per_layer:  int           = Field(..., gt=0)
    num_of_drawer_per_rack: int           = Field(..., gt=0)
    study_sample_capacity:  int           = Field(..., gt=0, description="Max study sample containers per drawer")
    stdqc_capacity:         int           = Field(..., gt=0, description="Max STDQC containers per drawer")
    description:            Optional[str] = None
    location:               Optional[str] = None


class FreezerResponse(BaseModel):
    """Freezer details returned after creation or listing."""
    id:                     int
    asset_id:               str
    temperature:            float
    num_of_layers:          int
    num_of_rack_per_layer:  int
    num_of_drawer_per_rack: int
    study_sample_capacity:  int
    stdqc_capacity:         int
    total_drawers:          int
    description:            Optional[str] = None
    location:               Optional[str] = None
    created_at:             datetime

    class Config:
        from_attributes = True
