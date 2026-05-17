from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Allocation (suggest phase)
# ---------------------------------------------------------------------------

class ContainerAllocationRequest(BaseModel):
    """Request to suggest drawer space for a batch of containers."""
    number_of_containers: int = Field(..., gt=0)
    sample_type:          Literal["study_sample_container", "stdqc_container"]
    freezer_asset_id:     str


class DrawerAllocation(BaseModel):
    """One row returned by the suggestion step — how many containers go in which drawer."""
    drawer_id:          int
    freezer_asset_id:   str
    layer_number:       int
    rack_number:        int
    drawer_number:      int
    drawer_coordinate:  str
    container_count:    int
    reservation_token:  str   # UUID — echo back in the confirm request
    expires_at:         datetime
    # Echoed back to the frontend so it can set partial_allowed correctly
    partial:            bool = False


# ---------------------------------------------------------------------------
# Confirmation (commit phase) — study sample containers
# ---------------------------------------------------------------------------

class StudySampleContainerDetail(BaseModel):
    """Full details for a single study sample container being confirmed."""
    container_barcode:  str
    study_name:         str
    position_in_drawer: Optional[str] = None


class StudySampleDrawerConfirmation(BaseModel):
    """
    The containers the user is committing to one specific drawer.
    drawer_id comes directly from the allocation suggestion.
    """
    drawer_id:  int
    containers: List[StudySampleContainerDetail] = Field(..., min_length=1)


class StudySampleAllocationConfirmRequest(BaseModel):
    """
    Confirmation payload for a study sample allocation.

    freezer_asset_id:   The freezer the allocation was suggested for.
                        Echoed back from the suggestion response so the confirm
                        endpoint can find alternative freezers when partial=True.
    originally_requested: Total containers requested in the allocation step.
                        Used to validate that the user isn't under-submitting
                        when partial_allowed=False, and to calculate how many
                        remain unplaced when partial_allowed=True.
    partial_allowed:    Must be True if the allocation step could not fit all
                        containers in the freezer. The frontend receives this
                        from the suggestion response and echoes it back.
    """
    freezer_asset_id:     str
    originally_requested: int = Field(..., gt=0)
    reservation_tokens:   List[str] = Field(
        ..., min_length=1,
        description="One token per drawer, in the same order as `drawers`. "
                    "Returned by the allocation suggestion step."
    )
    drawers:              List[StudySampleDrawerConfirmation] = Field(..., min_length=1)
    partial_allowed:      bool = False


# ---------------------------------------------------------------------------
# Confirmation (commit phase) — STDQC containers
#
# STDQC containers are introduced in bulk: the user provides one set of
# batch-level metadata (compound name, matrix, etc.) and a single barcode
# prefix plus a count. The API expands this into N individual rows, each
# sharing the same metadata and receiving an auto-suffixed barcode:
#   e.g. prefix "STD-001", count 3  ->  STD-001-1, STD-001-2, STD-001-3
# ---------------------------------------------------------------------------

class STDQCBatchDetail(BaseModel):
    """
    Metadata shared by all containers in a STDQC bulk introduction.

    barcode_prefix:  Common prefix for generated barcodes.
                     Each container receives <prefix>-<n> (1-indexed).
    container_count: How many containers are being placed in this drawer.
    """
    barcode_prefix:     str
    container_count:    int = Field(..., gt=0)
    compound_name:      str
    matrix:             str
    anticoagulant:      str
    prep_date:          datetime
    description:        Optional[str] = None
    position_in_drawer: Optional[str] = None


class STDQCDrawerConfirmation(BaseModel):
    """
    The STDQC batch the user is committing to one specific drawer.
    One batch per drawer — the allocation suggestion already split the
    count across drawers, so each drawer gets exactly one batch entry.
    """
    drawer_id: int
    batch:     STDQCBatchDetail


class STDQCAllocationConfirmRequest(BaseModel):
    """
    Confirmation payload for a STDQC bulk allocation.
    Same partial_allowed and freezer_asset_id logic as StudySampleAllocationConfirmRequest.
    """
    freezer_asset_id:     str
    originally_requested: int = Field(..., gt=0)
    reservation_tokens:   List[str] = Field(
        ..., min_length=1,
        description="One token per drawer, in the same order as `drawers`. "
                    "Returned by the allocation suggestion step."
    )
    drawers:              List[STDQCDrawerConfirmation] = Field(..., min_length=1)
    partial_allowed:      bool = False


# ---------------------------------------------------------------------------
# Confirmation response (shared)
# ---------------------------------------------------------------------------

class ConfirmedContainer(BaseModel):
    """One successfully inserted container row."""
    id:                 int
    drawer_id:          int
    drawer_coordinate:  str
    position_in_drawer: Optional[str] = None


class StudySampleConfirmedContainer(ConfirmedContainer):
    container_barcode: str
    study_name:        str


class STDQCConfirmedContainer(ConfirmedContainer):
    compound_name: str
    matrix:        str
    anticoagulant: str
    prep_date:     datetime
    source_id:     Optional[str] = None


class AllocationConfirmResponse(BaseModel):
    """
    Base confirmation response.

    total_confirmed:      How many containers were actually inserted.
    partial:              True when fewer containers were placed than requested
                          because the freezer ran out of space.
    alternative_freezers: Stub for future cross-freezer recommendation.
                          Will list asset_ids of same-temperature freezers
                          with enough remaining capacity when partial=True.
    containers:           The inserted rows, one per container.
    """
    total_confirmed:      int
    partial:              bool
    alternative_freezers: List[str] = Field(
        default_factory=list,
        description="asset_ids of same-temperature freezers with remaining "
                    "capacity (populated only when partial=True)"
    )
    containers: List[ConfirmedContainer]


class StudySampleConfirmResponse(AllocationConfirmResponse):
    """Confirmation response for study sample containers."""
    containers: List[StudySampleConfirmedContainer]


class STDQCConfirmResponse(AllocationConfirmResponse):
    """Confirmation response for STDQC containers."""
    containers: List[STDQCConfirmedContainer]


# ---------------------------------------------------------------------------
# Search / query responses
# ---------------------------------------------------------------------------

class DrawerLocation(BaseModel):
    """Full physical location of a drawer, joined from drawer_coordinates."""
    drawer_id:         int
    freezer_asset_id:  str
    layer_number:      int
    rack_number:       int
    drawer_number:     int
    drawer_coordinate: str


class StudySampleSearchResult(BaseModel):
    """
    One study sample container returned by a barcode lookup.
    Includes the container's own fields plus its physical drawer location.
    """
    id:                 int
    container_barcode:  str
    study_name:         str
    position_in_drawer: Optional[str] = None
    date_added:         datetime
    location:           DrawerLocation


class STDQCContainerResult(BaseModel):
    """One STDQC container row within a batch query result."""
    id:                 int
    source_id:          Optional[str] = None   # generated barcode e.g. STD-001-3
    position_in_drawer: Optional[str] = None
    date_added:         datetime
    location:           DrawerLocation


class STDQCBatchSearchResult(BaseModel):
    """
    All containers belonging to a STDQC batch, grouped by their shared metadata.
    A batch is identified by barcode_prefix (the prefix the user typed at introduction).
    Containers may span multiple drawers if the allocation split them.
    """
    barcode_prefix:  str
    compound_name:   str
    matrix:          str
    anticoagulant:   str
    prep_date:       datetime
    description:     Optional[str] = None
    total_count:     int
    containers:      List[STDQCContainerResult]


# ---------------------------------------------------------------------------
# Retrieval — study sample containers
# ---------------------------------------------------------------------------

class StudySampleRetrievalPreviewRequest(BaseModel):
    """
    Request to preview the locations of study sample containers before removal.
    The user provides the list of barcodes they intend to retrieve.
    """
    container_barcodes: List[str] = Field(..., min_length=1)


class StudySampleRetrievalPreviewItem(BaseModel):
    """One container returned in the retrieval preview."""
    id:                 int
    container_barcode:  str
    study_name:         str
    position_in_drawer: Optional[str] = None
    date_added:         datetime
    location:           DrawerLocation


class StudySampleRetrievalPreviewResponse(BaseModel):
    """
    Preview response showing where each requested container is located.
    Includes any barcodes that were not found so the user can review
    before confirming removal.
    """
    found:       List[StudySampleRetrievalPreviewItem]
    not_found:   List[str]   # barcodes that had no match in the DB
    total_found: int


class StudySampleRetrievalConfirmRequest(BaseModel):
    """
    Confirmation payload to permanently remove study sample containers.
    The user echoes back only the barcodes they actually retrieved —
    they may choose to remove a subset of what was previewed.
    """
    container_barcodes: List[str] = Field(..., min_length=1)


class RemovedContainer(BaseModel):
    """One successfully removed container."""
    id:                int
    container_barcode: str
    study_name:        str
    drawer_coordinate: str


class StudySampleRetrievalConfirmResponse(BaseModel):
    """Result of a confirmed study sample retrieval."""
    total_removed: int
    not_found:     List[str]   # barcodes submitted but not found (already removed?)
    removed:       List[RemovedContainer]


# ---------------------------------------------------------------------------
# Retrieval — STDQC containers
# ---------------------------------------------------------------------------

class STDQCRetrievalPreviewResponse(BaseModel):
    """
    Preview response showing all containers in a STDQC batch before removal.
    Reuses STDQCBatchSearchResult since the data shape is identical —
    the user sees the full batch with locations before confirming removal.
    """
    barcode_prefix: str
    compound_name:  str
    matrix:         str
    anticoagulant:  str
    prep_date:      datetime
    description:    Optional[str] = None
    total_count:    int
    containers:     List[STDQCContainerResult]


class STDQCRetrievalConfirmRequest(BaseModel):
    """
    Confirmation payload to permanently remove an entire STDQC batch.
    The barcode_prefix identifies the batch — all containers with
    source_ids matching '<prefix>-<n>' will be deleted.
    """
    barcode_prefix: str


class STDQCRetrievalConfirmResponse(BaseModel):
    """Result of a confirmed STDQC batch retrieval."""
    barcode_prefix: str
    total_removed:  int


# ---------------------------------------------------------------------------
# Manual assignment — study sample containers
#
# Direct write path — no reservation tokens, no two-stage flow.
# User selects a specific drawer and provides full container details.
# System validates capacity (respecting active reservations) and inserts
# immediately under an advisory lock.
# ---------------------------------------------------------------------------

class ManualStudySampleAssignRequest(BaseModel):
    """
    Payload for manually assigning study sample containers to a specific drawer.

    drawer_id:   The drawer the user has physically chosen.
    containers:  Full details for each container being placed.
                 Must not exceed effective available capacity
                 (capacity - actual containers - active reservations).
    """
    drawer_id:  int
    containers: List[StudySampleContainerDetail] = Field(..., min_length=1)


class ManualStudySampleAssignResponse(BaseModel):
    """Response after a successful manual study sample assignment."""
    drawer_id:         int
    drawer_coordinate: str
    total_assigned:    int
    containers:        List[StudySampleConfirmedContainer]


# ---------------------------------------------------------------------------
# Manual assignment — STDQC containers
# ---------------------------------------------------------------------------

class ManualSTDQCAssignRequest(BaseModel):
    """
    Payload for manually assigning a STDQC bulk batch to a specific drawer.

    drawer_id: The drawer the user has physically chosen.
    batch:     Shared metadata and count for the batch being placed.
               Must not exceed effective available capacity.
    """
    drawer_id:      int
    batch:          STDQCBatchDetail


class ManualSTDQCAssignResponse(BaseModel):
    """Response after a successful manual STDQC assignment."""
    drawer_id:         int
    drawer_coordinate: str
    total_assigned:    int
    containers:        List[STDQCConfirmedContainer]
