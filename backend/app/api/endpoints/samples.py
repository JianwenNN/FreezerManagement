from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app import schemas

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_location(row) -> dict:
    """Build a DrawerLocation dict from a drawer_coordinates row."""
    return {
        "drawer_id":         row.drawer_id,
        "freezer_asset_id":  row.freezer_asset_id,
        "layer_number":      row.layer_number,
        "rack_number":       row.rack_number,
        "drawer_number":     row.drawer_number,
        "drawer_coordinate": row.drawer_coordinate,
    }


# ---------------------------------------------------------------------------
# Study sample — lookup by container_barcode
# ---------------------------------------------------------------------------

@router.get(
    "/study-sample/{container_barcode}",
    response_model=schemas.StudySampleSearchResult,
)
def get_study_sample(
    container_barcode: str,
    db: Session = Depends(get_db),
):
    """
    Look up a single study sample container by its scanned barcode.
    Returns the container's stored details plus its full drawer location.
    """
    row = db.execute(
        text("""
            SELECT
                s.id,
                s.container_barcode,
                s.study_name,
                s.position_in_drawer,
                s.date_added,
                dc.drawer_id,
                dc.freezer_asset_id,
                dc.layer_number,
                dc.rack_number,
                dc.drawer_number,
                dc.drawer_coordinate
            FROM study_sample_container s
            JOIN drawer_coordinates dc ON s.drawer_id = dc.drawer_id
            WHERE s.container_barcode = :barcode
        """),
        {"barcode": container_barcode},
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No study sample container found with barcode '{container_barcode}'.",
        )

    return {
        "id":                 row.id,
        "container_barcode":  row.container_barcode,
        "study_name":         row.study_name,
        "position_in_drawer": row.position_in_drawer,
        "date_added":         row.date_added,
        "location":           _build_location(row),
    }


# ---------------------------------------------------------------------------
# STDQC — lookup by barcode_prefix (returns full batch)
# ---------------------------------------------------------------------------

@router.get(
    "/stdqc/",
    response_model=schemas.STDQCBatchSearchResult,
)
def get_stdqc_batch(
    barcode_prefix: str,
    db: Session = Depends(get_db),
):
    """
    Look up all STDQC containers belonging to a batch by its barcode prefix.
    Returns shared batch metadata plus every container with its drawer location.
    """
    rows = db.execute(
        text("""
            SELECT
                s.id,
                s.source_id,
                s.compound_name,
                s.matrix,
                s.anticoagulant,
                s.prep_date,
                s.description,
                s.position_in_drawer,
                s.date_added,
                dc.drawer_id,
                dc.freezer_asset_id,
                dc.layer_number,
                dc.rack_number,
                dc.drawer_number,
                dc.drawer_coordinate
            FROM stdqc_container s
            JOIN drawer_coordinates dc ON s.drawer_id = dc.drawer_id
            WHERE s.source_id LIKE :prefix_pattern
            ORDER BY CAST(
                SPLIT_PART(s.source_id, '-', ARRAY_LENGTH(STRING_TO_ARRAY(s.source_id, '-'), 1))
            AS INTEGER)
        """),
        {"prefix_pattern": f"{barcode_prefix}-%"},
    ).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No STDQC batch found with prefix '{barcode_prefix}'.",
        )

    first = rows[0]

    return {
        "barcode_prefix": barcode_prefix,
        "compound_name":  first.compound_name,
        "matrix":         first.matrix,
        "anticoagulant":  first.anticoagulant,
        "prep_date":      first.prep_date,
        "description":    first.description,
        "total_count":    len(rows),
        "containers": [
            {
                "id":                 r.id,
                "source_id":          r.source_id,
                "position_in_drawer": r.position_in_drawer,
                "date_added":         r.date_added,
                "location":           _build_location(r),
            }
            for r in rows
        ],
    }
