import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Callable, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app import schemas
from app.models import StudySampleContainer, STDQCContainer, DrawerReservation

router = APIRouter()

RESERVATION_TTL_MINUTES = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_reservation(
    db:            Session,
    drawer_id:     int,
    sample_type:   str,
    count:         int,
) -> DrawerReservation:
    """
    Create a soft-hold reservation for a drawer allocation.
    Committed immediately — the reservation itself is short-lived data,
    not part of the container insert transaction.
    """
    reservation = DrawerReservation(
        drawer_id      = drawer_id,
        sample_type    = sample_type,
        reserved_count = count,
        token          = str(uuid.uuid4()),
        expires_at     = datetime.now(timezone.utc) + timedelta(minutes=RESERVATION_TTL_MINUTES),
    )
    db.add(reservation)
    db.flush()
    return reservation


def _resolve_reservation(
    db:          Session,
    drawer_id:   int,
    sample_type: str,
    token:       str,
) -> tuple[bool, str | None]:
    """
    Validate a reservation token.

    Returns (is_valid, reason):
      - (True, None)                  → reservation found and not expired
      - (False, 'expired')            → token found but expired; caller should re-check capacity
      - (False, 'not_found')          → token not found at all
      - (False, 'drawer_mismatch')    → token exists but belongs to a different drawer
    """
    reservation = db.execute(
        text("""
            SELECT id, drawer_id, sample_type, reserved_count, expires_at
            FROM   drawer_reservation
            WHERE  token = :token
        """),
        {"token": token}
    ).fetchone()

    if not reservation:
        return False, "not_found"

    if reservation.drawer_id != drawer_id:
        return False, "drawer_mismatch"

    if reservation.expires_at.astimezone(timezone.utc) < datetime.now(timezone.utc):
        return False, "expired"

    return True, None


def _delete_reservation(db: Session, token: str) -> None:
    """Remove a reservation after successful confirmation."""
    db.execute(
        text("DELETE FROM drawer_reservation WHERE token = :token"),
        {"token": token}
    )


# ---------------------------------------------------------------------------
# Suggest — creates reservations, returns tokens
# ---------------------------------------------------------------------------

@router.post("/allocate-proximity/", response_model=List[schemas.DrawerAllocation])
def allocate_containers_in_proximity(
    request: schemas.ContainerAllocationRequest,
    db: Session = Depends(get_db)
):
    """
    Suggest which drawers to use for a batch of containers and create
    soft-hold reservations for each drawer.
    """
    results = db.execute(
        text("""
            SELECT * FROM allocate_containers_in_proximity(
                :container_count, :sample_type, :freezer_asset_id
            )
        """),
        {
            "container_count":  request.number_of_containers,
            "sample_type":      request.sample_type,
            "freezer_asset_id": request.freezer_asset_id,
        }
    ).fetchall()

    if not results:
        raise HTTPException(
            status_code=400,
            detail="No space available for the requested containers in this freezer."
        )

    total_allocated = sum(row.container_count for row in results)
    is_partial      = total_allocated < request.number_of_containers

    # Batch-fetch drawer details in one query
    drawer_ids = [row.drawer_id for row in results]
    drawer_details = {
        row.drawer_id: row
        for row in db.execute(
            text("""
                SELECT drawer_id, freezer_asset_id, layer_number,
                       rack_number, drawer_number, drawer_coordinate
                FROM drawer_coordinates
                WHERE drawer_id = ANY(:ids)
            """),
            {"ids": drawer_ids}
        ).fetchall()
    }

    reservations = {
        row.drawer_id: _create_reservation(
            db, row.drawer_id, request.sample_type, row.container_count
        )
        for row in results
    }
    db.commit()

    allocations = []
    for row in results:
        detail      = drawer_details[row.drawer_id]
        reservation = reservations[row.drawer_id]
        allocations.append({
            "drawer_id":         row.drawer_id,
            "freezer_asset_id":  detail.freezer_asset_id,
            "layer_number":      detail.layer_number,
            "rack_number":       detail.rack_number,
            "drawer_number":     detail.drawer_number,
            "drawer_coordinate": row.drawer_coordinate,
            "container_count":   row.container_count,
            "reservation_token": reservation.token,
            "expires_at":        reservation.expires_at,
            "partial":           is_partial,
        })

    return allocations


# ---------------------------------------------------------------------------
# Internal: per-drawer critical section (used by both confirm endpoints)
# ---------------------------------------------------------------------------

def _confirm_drawer(
    db:                  Session,
    drawer_id:           int,
    sample_type:         str,
    token:               str,
    containers_to_insert: int,
) -> None:
    """
    Short critical section for one drawer:
      1. Acquire advisory lock (milliseconds, released on commit)
      2. Validate or re-check capacity
      3. Delete the reservation
    """
    db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": drawer_id})

    drawer = db.execute(
        text("SELECT id, reserved FROM drawer WHERE id = :id"),
        {"id": drawer_id}
    ).fetchone()

    if not drawer:
        raise HTTPException(status_code=404, detail=f"Drawer {drawer_id} not found.")
    if drawer.reserved:
        raise HTTPException(
            status_code=409,
            detail=f"Drawer {drawer_id} is reserved and cannot accept containers."
        )

    is_valid, reason = _resolve_reservation(db, drawer_id, sample_type, token)

    if not is_valid:
        if reason == "not_found":
            raise HTTPException(
                status_code=409,
                detail=f"Reservation token for drawer {drawer_id} not found. Please re-run the allocation."
            )
        if reason == "drawer_mismatch":
            raise HTTPException(
                status_code=409,
                detail=f"Reservation token does not match drawer {drawer_id}."
            )

    _delete_reservation(db, token)

    remaining_space = db.execute(
        text("SELECT available_space_in_drawer(:drawer_id, :sample_type)"),
        {"drawer_id": drawer_id, "sample_type": sample_type}
    ).scalar()

    if containers_to_insert > remaining_space:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Drawer {drawer_id} only has space for {remaining_space} more "
                f"{'containers' if remaining_space != 1 else 'container'}, "
                f"but {containers_to_insert} were submitted."
                + (" Reservation had expired — space was claimed by another user."
                   if reason == "expired" else "")
            ).strip()
        )


# ---------------------------------------------------------------------------
# Internal Pipeline Orchestrator (Eliminates Duplication)
# ---------------------------------------------------------------------------

def _confirm_allocation_pipeline(
    db: Session,
    request: Any,
    sample_type: str,
    get_count_func: Callable[[Any], int],
    insert_func: Callable[[int, Any], List[Any]]
) -> tuple[List[Any], dict[int, str], List[str]]:
    """
    Shared orchestration logic for validating, locking, and processing drawer confirmations.
    
    Args:
        get_count_func: Sub-routine to calculate incoming containers for a specific drawer.
        insert_func: Sub-routine handling specific ORM model initialization and database flushes.
    """
    # 1. Under-submission guard
    total_submitted = sum(get_count_func(d) for d in request.drawers)
    if not request.partial_allowed and total_submitted != request.originally_requested:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Expected {request.originally_requested} containers but {total_submitted} were submitted. "
                f"Set partial_allowed=True if the freezer could not fit all containers."
            )
        )

    if len(request.reservation_tokens) != len(request.drawers):
        raise HTTPException(
            status_code=422,
            detail="reservation_tokens must have one entry per drawer in the same order as drawers."
        )

    confirmed_rows = []

    # 2. Main lock & insertion loop
    for drawer_confirmation, token in zip(request.drawers, request.reservation_tokens):
        drawer_id = drawer_confirmation.drawer_id
        containers_to_insert = get_count_func(drawer_confirmation)

        _confirm_drawer(db, drawer_id, sample_type, token, containers_to_insert)
        
        # Call type-specific DB insertion logic passed from the route
        inserted = insert_func(drawer_id, drawer_confirmation)
        confirmed_rows.extend(inserted)

    db.commit()

    # 3. Batch-resolve drawer coordinates
    drawer_ids = list({r.drawer_id for r in confirmed_rows})
    coordinates = {
        row.drawer_id: row.drawer_coordinate
        for row in db.execute(
            text("""
                SELECT drawer_id, drawer_coordinate
                FROM drawer_coordinates
                WHERE drawer_id = ANY(:ids)
            """),
            {"ids": drawer_ids}
        ).fetchall()
    }

    alternative_freezers = (
        _find_alternative_freezers(db, request, len(confirmed_rows)) if request.partial_allowed else []
    )

    return confirmed_rows, coordinates, alternative_freezers


# ---------------------------------------------------------------------------
# Confirm — study sample containers
# ---------------------------------------------------------------------------

@router.post(
    "/confirm/study-sample/",
    response_model=schemas.StudySampleConfirmResponse,
)
def confirm_study_sample_allocation(
    request: schemas.StudySampleAllocationConfirmRequest,
    db: Session = Depends(get_db)
):
    """Commit a study sample allocation to the database."""
    
    def insert_study_samples(drawer_id: int, confirmation: Any) -> List[StudySampleContainer]:
        batch_rows = []
        for container in confirmation.containers:
            row = StudySampleContainer(
                drawer_id          = drawer_id,
                container_barcode  = container.container_barcode,
                study_name         = container.study_name,
                position_in_drawer = container.position_in_drawer,
            )
            db.add(row)
            db.flush()
            batch_rows.append(row)
        return batch_rows

    confirmed, coordinates, alternative_freezers = _confirm_allocation_pipeline(
        db=db,
        request=request,
        sample_type="study_sample_container",
        get_count_func=lambda d: len(d.containers),
        insert_func=insert_study_samples
    )

    return {
        "total_confirmed":      len(confirmed),
        "partial":              request.partial_allowed,
        "alternative_freezers": alternative_freezers,
        "containers": [
            {
                "id":                 r.id,
                "drawer_id":          r.drawer_id,
                "drawer_coordinate":  coordinates[r.drawer_id],
                "container_barcode":  r.container_barcode,
                "study_name":         r.study_name,
                "position_in_drawer": r.position_in_drawer,
            }
            for r in confirmed
        ],
    }


# ---------------------------------------------------------------------------
# Confirm — STDQC containers
# ---------------------------------------------------------------------------

@router.post(
    "/confirm/stdqc/",
    response_model=schemas.STDQCConfirmResponse,
)
def confirm_stdqc_allocation(
    request: schemas.STDQCAllocationConfirmRequest,
    db: Session = Depends(get_db)
):
    """Commit a STDQC allocation to the database."""
    
    # Track across drawer iterations to avoid resetting barcode prefix suffix sequence
    state = {"barcode_counter": 1}

    def insert_stdqc_samples(drawer_id: int, confirmation: Any) -> List[STDQCContainer]:
        batch_rows = []
        batch = confirmation.batch
        for _ in range(batch.container_count):
            row = STDQCContainer(
                drawer_id          = drawer_id,
                compound_name      = batch.compound_name,
                matrix             = batch.matrix,
                anticoagulant      = batch.anticoagulant,
                prep_date          = batch.prep_date,
                source_id          = f"{batch.barcode_prefix}-{state['barcode_counter']}",
                description        = batch.description,
                position_in_drawer = batch.position_in_drawer,
            )
            db.add(row)
            db.flush()
            batch_rows.append(row)
            state["barcode_counter"] += 1
        return batch_rows

    confirmed, coordinates, alternative_freezers = _confirm_allocation_pipeline(
        db=db,
        request=request,
        sample_type="stdqc_container",
        get_count_func=lambda d: d.batch.container_count,
        insert_func=insert_stdqc_samples
    )

    return {
        "total_confirmed":      len(confirmed),
        "partial":              request.partial_allowed,
        "alternative_freezers": alternative_freezers,
        "containers": [
            {
                "id":                 r.id,
                "drawer_id":          r.drawer_id,
                "drawer_coordinate":  coordinates[r.drawer_id],
                "compound_name":      r.compound_name,
                "matrix":             r.matrix,
                "anticoagulant":      r.anticoagulant,
                "prep_date":          r.prep_date,
                "source_id":          r.source_id,
                "position_in_drawer": r.position_in_drawer,
            }
            for r in confirmed
        ],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_alternative_freezers(db: Session, request, confirmed_count: int) -> List[str]:
    """
    Stub: returns asset_ids of freezers at the same temperature that have
    enough remaining space for the unplaced containers.
    """
    return []