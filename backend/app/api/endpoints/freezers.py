from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models import Freezer, Layer, Rack, Drawer
from app import schemas

router = APIRouter()


# ---------------------------------------------------------------------------
# Create freezer
# ---------------------------------------------------------------------------

@router.post("/", response_model=schemas.FreezerResponse, status_code=201)
def create_freezer(
    request: schemas.FreezerCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new freezer and auto-generate its full physical structure.

    Everything happens in one transaction:
      1. Validate asset_id is unique.
      2. Insert the freezer row (with capacity columns).
      3. Generate all layers → racks → drawers.

    Drawers start typeless. The first container placed in a drawer locks
    it to that sample type; emptying the drawer makes it flexible again.
    """
    # Guard: asset_id must be unique
    existing = db.execute(
        text("SELECT id FROM freezer WHERE asset_id = :asset_id"),
        {"asset_id": request.asset_id}
    ).fetchone()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A freezer with asset_id '{request.asset_id}' already exists."
        )

    # Step 1: insert freezer row
    freezer = Freezer(
        asset_id               = request.asset_id,
        temperature            = request.temperature,
        num_of_layers          = request.num_of_layers,
        num_of_rack_per_layer  = request.num_of_rack_per_layer,
        num_of_drawer_per_rack = request.num_of_drawer_per_rack,
        study_sample_capacity  = request.study_sample_capacity,
        stdqc_capacity         = request.stdqc_capacity,
        description            = request.description,
        location               = request.location,
    )
    db.add(freezer)
    db.flush()  # get freezer.id

    # Step 2: generate layers → racks → drawers
    for layer_num in range(1, request.num_of_layers + 1):
        layer = Layer(
            freezer_id   = freezer.id,
            layer_number = layer_num,
        )
        db.add(layer)
        db.flush()  # get layer.id

        for rack_num in range(1, request.num_of_rack_per_layer + 1):
            rack = Rack(
                layer_id    = layer.id,
                rack_number = rack_num,
            )
            db.add(rack)
            db.flush()  # get rack.id

            for drawer_num in range(1, request.num_of_drawer_per_rack + 1):
                db.add(Drawer(
                    rack_id       = rack.id,
                    drawer_number = drawer_num,
                ))

    db.commit()
    db.refresh(freezer)

    total_drawers = (
        request.num_of_layers
        * request.num_of_rack_per_layer
        * request.num_of_drawer_per_rack
    )

    return {
        "id":                     freezer.id,
        "asset_id":               freezer.asset_id,
        "temperature":            float(freezer.temperature),
        "num_of_layers":          freezer.num_of_layers,
        "num_of_rack_per_layer":  freezer.num_of_rack_per_layer,
        "num_of_drawer_per_rack": freezer.num_of_drawer_per_rack,
        "study_sample_capacity":  freezer.study_sample_capacity,
        "stdqc_capacity":         freezer.stdqc_capacity,
        "total_drawers":          total_drawers,
        "description":            freezer.description,
        "location":               freezer.location,
        "created_at":             freezer.created_at,
    }


# ---------------------------------------------------------------------------
# List all freezers
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[schemas.FreezerResponse])
def list_freezers(db: Session = Depends(get_db)):
    """Return all registered freezers ordered by creation date."""
    rows = db.execute(
        text("""
            SELECT
                id,
                asset_id,
                temperature,
                num_of_layers,
                num_of_rack_per_layer,
                num_of_drawer_per_rack,
                study_sample_capacity,
                stdqc_capacity,
                num_of_layers * num_of_rack_per_layer * num_of_drawer_per_rack
                    AS total_drawers,
                description,
                location,
                created_at
            FROM freezer
            ORDER BY created_at DESC
        """)
    ).fetchall()

    return [
        {
            "id":                     f.id,
            "asset_id":               f.asset_id,
            "temperature":            float(f.temperature),
            "num_of_layers":          f.num_of_layers,
            "num_of_rack_per_layer":  f.num_of_rack_per_layer,
            "num_of_drawer_per_rack": f.num_of_drawer_per_rack,
            "study_sample_capacity":  f.study_sample_capacity,
            "stdqc_capacity":         f.stdqc_capacity,
            "total_drawers":          f.total_drawers,
            "description":            f.description,
            "location":               f.location,
            "created_at":             f.created_at,
        }
        for f in rows
    ]
