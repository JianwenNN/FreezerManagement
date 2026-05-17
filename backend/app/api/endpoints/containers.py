import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

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
) -> Tuple[bool, Optional[str]]:
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

    The response includes one `reservation_token` per drawer. The frontend
    must echo these tokens back in the confirm request. Reservations expire
    after 5 minutes; expired reservations trigger a live capacity re-check
    at confirmation time rather than an outright rejection.

    Nothing other than the reservation rows is written at this stage.
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

    # Create a reservation for each drawer and commit them all at once.
    # This is a separate commit from the container inserts — the reservation
    # lifetime is independent of the confirmation transaction.
    reservations: Dict[int, DrawerReservation] = {}
    for row in results:
        reservation = _create_reservation(
            db, row.drawer_id, request.sample_type, row.container_count
        )
        reservations[row.drawer_id] = reservation
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

def _acquire_drawer_lock(db: Session, drawer_id: int) -> None:
    """
    Acquire a transaction-scoped advisory lock on drawer_id.
    Blocks any other transaction attempting the same lock until this
    transaction commits or rolls back — typically milliseconds.
    """
    db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": drawer_id})


def _validate_drawer(db: Session, drawer_id: int) -> None:
    """
    Confirm the drawer exists and is not administratively reserved.
    Raises HTTPException on failure.
    """
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


def _check_capacity(
    db:                  Session,
    drawer_id:           int,
    sample_type:         str,
    containers_to_insert: int,
    expired_reservation: bool = False,
) -> None:
    """
    Verify effective available space >= containers_to_insert.
    effective_available = capacity - actual_containers - active_reservations

    Must be called AFTER any reservation for this drawer has been deleted
    from the current transaction, otherwise the caller's own reservation
    would be subtracted from their own available space.

    Raises HTTPException(409) if capacity is insufficient.
    """
    remaining_space = db.execute(
        text("SELECT available_space_in_drawer(:drawer_id, :sample_type)"),
        {"drawer_id": drawer_id, "sample_type": sample_type}
    ).scalar()

    if containers_to_insert > remaining_space:
        detail = (
            f"Drawer {drawer_id} only has space for {remaining_space} more "
            f"{'containers' if remaining_space != 1 else 'container'}, "
            f"but {containers_to_insert} were submitted."
        )
        if expired_reservation:
            detail += " Reservation had expired — space was claimed by another user."
        raise HTTPException(status_code=409, detail=detail.strip())


def _confirm_drawer(
    db:                  Session,
    drawer_id:           int,
    sample_type:         str,
    token:               str,
    containers_to_insert: int,
) -> None:
    """
    Short critical section for the reservation-based confirm flow:
      1. Acquire advisory lock
      2. Validate drawer exists and is not reserved
      3. Validate reservation token (or note expiry)
      4. Delete reservation (before capacity check — see _check_capacity docstring)
      5. Check effective available capacity
    Inserts are done by the caller after this returns.
    """
    _acquire_drawer_lock(db, drawer_id)
    _validate_drawer(db, drawer_id)

    # Validate the reservation token
    is_valid, reason = _resolve_reservation(db, drawer_id, sample_type, token)

    if not is_valid:
        if reason == "not_found":
            raise HTTPException(
                status_code=409,
                detail=f"Reservation token for drawer {drawer_id} not found. "
                       f"Please re-run the allocation."
            )
        if reason == "drawer_mismatch":
            raise HTTPException(
                status_code=409,
                detail=f"Reservation token does not match drawer {drawer_id}."
            )
        # reason == 'expired': fall through — delete reservation and re-check capacity

    # Delete reservation BEFORE capacity check (see _check_capacity docstring)
    _delete_reservation(db, token)
    _check_capacity(db, drawer_id, sample_type, containers_to_insert,
                    expired_reservation=(reason == "expired"))


def _manual_validate_drawer(
    db:                  Session,
    drawer_id:           int,
    sample_type:         str,
    containers_to_insert: int,
) -> None:
    """
    Critical section for the manual assignment flow (no reservation token):
      1. Acquire advisory lock
      2. Validate drawer exists and is not reserved
      3. Check effective available capacity (respects active reservations)
    Inserts are done by the caller after this returns.
    """
    _acquire_drawer_lock(db, drawer_id)
    _validate_drawer(db, drawer_id)
    _check_capacity(db, drawer_id, sample_type, containers_to_insert)


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
    """
    Commit a study sample allocation to the database.

    For each drawer:
      1. Acquire a per-drawer advisory lock (released on commit)
      2. Validate the reservation token (or re-check capacity if expired)
      3. Re-check live capacity
      4. Insert containers
      5. Delete reservation

    The entire operation is one short transaction committed immediately.
    """
    # Under-submission guard
    total_submitted = sum(len(d.containers) for d in request.drawers)
    if not request.partial_allowed and total_submitted != request.originally_requested:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Expected {request.originally_requested} containers "
                f"but {total_submitted} were submitted. "
                f"Set partial_allowed=True if the freezer could not fit all containers."
            )
        )

    if len(request.reservation_tokens) != len(request.drawers):
        raise HTTPException(
            status_code=422,
            detail="reservation_tokens must have one entry per drawer in the same order as drawers."
        )

    confirmed = []

    for drawer_confirmation, token in zip(request.drawers, request.reservation_tokens):
        drawer_id            = drawer_confirmation.drawer_id
        containers_to_insert = len(drawer_confirmation.containers)

        _confirm_drawer(db, drawer_id, "study_sample_container", token, containers_to_insert)

        for container in drawer_confirmation.containers:
            confirmed.extend(
                _insert_study_sample_containers(db, drawer_id, [container])
            )

    db.commit()

    coordinates = _resolve_coordinates(db, confirmed)
    alternative_freezers = (
        _find_alternative_freezers(db, request, len(confirmed)) if request.partial_allowed else []
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
    """
    Commit a STDQC allocation to the database.
    Same reservation validation and critical-section logic as study samples.
    """
    # Under-submission guard
    total_submitted = sum(d.batch.container_count for d in request.drawers)
    if not request.partial_allowed and total_submitted != request.originally_requested:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Expected {request.originally_requested} containers "
                f"but {total_submitted} were submitted. "
                f"Set partial_allowed=True if the freezer could not fit all containers."
            )
        )

    if len(request.reservation_tokens) != len(request.drawers):
        raise HTTPException(
            status_code=422,
            detail="reservation_tokens must have one entry per drawer in the same order as drawers."
        )

    confirmed    = []
    barcode_counter = 1

    for drawer_confirmation, token in zip(request.drawers, request.reservation_tokens):
        drawer_id            = drawer_confirmation.drawer_id
        batch                = drawer_confirmation.batch
        containers_to_insert = batch.container_count

        _confirm_drawer(db, drawer_id, "stdqc_container", token, containers_to_insert)

        new_rows, barcode_counter = _insert_stdqc_containers(
            db, drawer_id, batch, barcode_counter
        )
        confirmed.extend(new_rows)

    db.commit()

    coordinates = _resolve_coordinates(db, confirmed)
    alternative_freezers = (
        _find_alternative_freezers(db, request, len(confirmed)) if request.partial_allowed else []
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

def _insert_study_sample_containers(
    db:         Session,
    drawer_id:  int,
    containers: list,
) -> list:
    """
    Insert study sample container rows and return the flushed ORM objects.
    Caller is responsible for db.commit().
    """
    rows = []
    for container in containers:
        row = StudySampleContainer(
            drawer_id          = drawer_id,
            container_barcode  = container.container_barcode,
            study_name         = container.study_name,
            position_in_drawer = container.position_in_drawer,
        )
        db.add(row)
        db.flush()
        rows.append(row)
    return rows


def _insert_stdqc_containers(
    db:              Session,
    drawer_id:       int,
    batch,
    start_counter:   int,
) -> tuple:
    """
    Insert STDQC container rows for a batch and return (rows, next_counter).
    Barcodes are generated as <prefix>-<start_counter>, <prefix>-<start_counter+1>, ...
    Caller is responsible for db.commit().
    """
    rows = []
    counter = start_counter
    for _ in range(batch.container_count):
        row = STDQCContainer(
            drawer_id          = drawer_id,
            compound_name      = batch.compound_name,
            matrix             = batch.matrix,
            anticoagulant      = batch.anticoagulant,
            prep_date          = batch.prep_date,
            source_id          = f"{batch.barcode_prefix}-{counter}",
            description        = batch.description,
            position_in_drawer = batch.position_in_drawer,
        )
        db.add(row)
        db.flush()
        rows.append(row)
        counter += 1
    return rows, counter


def _resolve_coordinates(db: Session, confirmed: list) -> dict:
    """
    Batch-fetch drawer coordinates for a list of inserted container rows.
    Returns {drawer_id: drawer_coordinate}.
    """
    drawer_ids = list({r.drawer_id for r in confirmed})
    return {
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



def _insert_study_sample_containers(
    db:         Session,
    drawer_id:  int,
    containers: list,
) -> list:
    """
    Insert study sample container rows and return the flushed ORM objects.
    Caller is responsible for db.commit().
    """
    rows = []
    for container in containers:
        row = StudySampleContainer(
            drawer_id          = drawer_id,
            container_barcode  = container.container_barcode,
            study_name         = container.study_name,
            position_in_drawer = container.position_in_drawer,
        )
        db.add(row)
        db.flush()
        rows.append(row)
    return rows


def _insert_stdqc_containers(
    db:            Session,
    drawer_id:     int,
    batch,
    start_counter: int,
) -> tuple:
    """
    Insert STDQC container rows for a batch and return (rows, next_counter).
    Barcodes are generated as <prefix>-<start_counter>, <prefix>-<start_counter+1>, ...
    Caller is responsible for db.commit().
    """
    rows = []
    counter = start_counter
    for _ in range(batch.container_count):
        row = STDQCContainer(
            drawer_id          = drawer_id,
            compound_name      = batch.compound_name,
            matrix             = batch.matrix,
            anticoagulant      = batch.anticoagulant,
            prep_date          = batch.prep_date,
            source_id          = f"{batch.barcode_prefix}-{counter}",
            description        = batch.description,
            position_in_drawer = batch.position_in_drawer,
        )
        db.add(row)
        db.flush()
        rows.append(row)
        counter += 1
    return rows, counter


def _resolve_coordinates(db: Session, confirmed: list) -> dict:
    """
    Batch-fetch drawer coordinates for a list of inserted container rows.
    Returns {drawer_id: drawer_coordinate}.
    """
    drawer_ids = list({r.drawer_id for r in confirmed})
    return {
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

def _find_alternative_freezers(db: Session, request, confirmed_count: int) -> List[str]:
    """
    Stub: returns asset_ids of freezers at the same temperature that have
    enough remaining space for the unplaced containers.

    TODO: implement when cross-freezer recommendation is scoped.
          Required fields now available on request:
          - request.freezer_asset_id: the original freezer
          - request.originally_requested: total containers requested
          - confirmed_count: how many were actually placed
          Remaining = originally_requested - confirmed_count
    """
    return []


# ---------------------------------------------------------------------------
# Manual assignment — study sample containers
# ---------------------------------------------------------------------------

@router.post(
    "/manual/study-sample/",
    response_model=schemas.ManualStudySampleAssignResponse,
    status_code=201,
)
def manual_assign_study_samples(
    request: schemas.ManualStudySampleAssignRequest,
    db: Session = Depends(get_db)
):
    """
    Manually assign study sample containers to a specific drawer.

    Does NOT participate in the reservation system — no token required.
    Respects active reservations: effective available space is
    capacity - actual_containers - active_reservations.

    All validation and inserts happen in one short transaction
    protected by a per-drawer advisory lock.
    """
    drawer_id            = request.drawer_id
    containers_to_insert = len(request.containers)

    _manual_validate_drawer(db, drawer_id, "study_sample_container", containers_to_insert)

    confirmed = _insert_study_sample_containers(db, drawer_id, request.containers)

    db.commit()

    coordinates = _resolve_coordinates(db, confirmed)
    drawer_coordinate = coordinates[drawer_id]

    return {
        "drawer_id":         drawer_id,
        "drawer_coordinate": drawer_coordinate,
        "total_assigned":    len(confirmed),
        "containers": [
            {
                "id":                 r.id,
                "drawer_id":          r.drawer_id,
                "drawer_coordinate":  drawer_coordinate,
                "container_barcode":  r.container_barcode,
                "study_name":         r.study_name,
                "position_in_drawer": r.position_in_drawer,
            }
            for r in confirmed
        ],
    }


# ---------------------------------------------------------------------------
# Manual assignment — STDQC containers
# ---------------------------------------------------------------------------

@router.post(
    "/manual/stdqc/",
    response_model=schemas.ManualSTDQCAssignResponse,
    status_code=201,
)
def manual_assign_stdqc(
    request: schemas.ManualSTDQCAssignRequest,
    db: Session = Depends(get_db)
):
    """
    Manually assign a STDQC batch to a specific drawer.

    Same rules as manual study sample assignment — no reservation token,
    respects active reservations, advisory lock, immediate commit.
    """
    drawer_id            = request.drawer_id
    batch                = request.batch
    containers_to_insert = batch.container_count

    _manual_validate_drawer(db, drawer_id, "stdqc_container", containers_to_insert)

    # Start barcode counter from the next available suffix for this prefix
    # to avoid collisions if the prefix was used before in this drawer.
    existing_count = db.execute(
        text("""
            SELECT COUNT(*) FROM stdqc_container
            WHERE source_id LIKE :pattern
        """),
        {"pattern": f"{batch.barcode_prefix}-%"}
    ).scalar() or 0

    confirmed, _ = _insert_stdqc_containers(db, drawer_id, batch, start_counter=existing_count + 1)

    db.commit()

    coordinates = _resolve_coordinates(db, confirmed)
    drawer_coordinate = coordinates[drawer_id]

    return {
        "drawer_id":         drawer_id,
        "drawer_coordinate": drawer_coordinate,
        "total_assigned":    len(confirmed),
        "containers": [
            {
                "id":                 r.id,
                "drawer_id":          r.drawer_id,
                "drawer_coordinate":  drawer_coordinate,
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
