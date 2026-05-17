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


def _escape_like(value: str) -> str:
    """
    Escape LIKE special characters in a user-provided string.
    Prevents a prefix like 'STD_%' from matching unintended source_ids.
    """
    value = value.replace("\\", "\\\\")
    value = value.replace("%", "\\%")
    value = value.replace("_", "\\_")
    return value


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
        {"prefix_pattern": f"{_escape_like(barcode_prefix)}-%"},
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


# ---------------------------------------------------------------------------
# Study sample retrieval — preview
# ---------------------------------------------------------------------------

@router.post(
    "/study-sample/retrieval-preview",
    response_model=schemas.StudySampleRetrievalPreviewResponse,
)
def preview_study_sample_retrieval(
    request: schemas.StudySampleRetrievalPreviewRequest,
    db: Session = Depends(get_db),
):
    """
    Preview the locations of study sample containers before removing them.

    Accepts a list of container barcodes. Returns the full location of each
    found container plus a list of any barcodes that were not found.
    Nothing is deleted at this stage.
    """
    rows = db.execute(
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
            WHERE s.container_barcode = ANY(:barcodes)
            ORDER BY dc.drawer_coordinate, s.container_barcode
        """),
        {"barcodes": request.container_barcodes},
    ).fetchall()

    found_barcodes = {row.container_barcode for row in rows}
    not_found      = [b for b in request.container_barcodes if b not in found_barcodes]

    return {
        "found": [
            {
                "id":                 row.id,
                "container_barcode":  row.container_barcode,
                "study_name":         row.study_name,
                "position_in_drawer": row.position_in_drawer,
                "date_added":         row.date_added,
                "location":           _build_location(row),
            }
            for row in rows
        ],
        "not_found":   not_found,
        "total_found": len(rows),
    }


# ---------------------------------------------------------------------------
# Study sample retrieval — confirm
# ---------------------------------------------------------------------------

@router.post(
    "/study-sample/retrieval-confirm",
    response_model=schemas.StudySampleRetrievalConfirmResponse,
)
def confirm_study_sample_retrieval(
    request: schemas.StudySampleRetrievalConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    Permanently remove study sample containers from the system.

    The user provides the barcodes they actually retrieved (may be a subset
    of what was previewed). Each matching container is deleted, freeing its
    space in the drawer. Barcodes not found are reported but do not cause failure.

    All deletes happen in one transaction.
    """
    # Fetch all matching rows first so we can build the response
    rows = db.execute(
        text("""
            SELECT
                s.id,
                s.container_barcode,
                s.study_name,
                s.drawer_id,
                dc.drawer_coordinate
            FROM study_sample_container s
            JOIN drawer_coordinates dc ON s.drawer_id = dc.drawer_id
            WHERE s.container_barcode = ANY(:barcodes)
        """),
        {"barcodes": request.container_barcodes},
    ).fetchall()

    found_barcodes = {row.container_barcode for row in rows}
    not_found      = [b for b in request.container_barcodes if b not in found_barcodes]

    if rows:
        db.execute(
            text("""
                DELETE FROM study_sample_container
                WHERE container_barcode = ANY(:barcodes)
            """),
            {"barcodes": request.container_barcodes},
        )
        db.commit()

    return {
        "total_removed": len(rows),
        "not_found":     not_found,
        "removed": [
            {
                "id":                row.id,
                "container_barcode": row.container_barcode,
                "study_name":        row.study_name,
                "drawer_coordinate": row.drawer_coordinate,
            }
            for row in rows
        ],
    }


# ---------------------------------------------------------------------------
# STDQC retrieval — preview
# ---------------------------------------------------------------------------

@router.get(
    "/stdqc/retrieval-preview",
    response_model=schemas.STDQCRetrievalPreviewResponse,
)
def preview_stdqc_retrieval(
    barcode_prefix: str,
    db: Session = Depends(get_db),
):
    """
    Preview all containers in a STDQC batch before removing them.

    Returns the full batch with all container locations. Nothing is deleted.
    The user uses this to physically locate all containers in the freezer
    before confirming removal.
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
        {"prefix_pattern": f"{_escape_like(barcode_prefix)}-%"},
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


# ---------------------------------------------------------------------------
# STDQC retrieval — confirm
# ---------------------------------------------------------------------------

@router.post(
    "/stdqc/retrieval-confirm",
    response_model=schemas.STDQCRetrievalConfirmResponse,
)
def confirm_stdqc_retrieval(
    request: schemas.STDQCRetrievalConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    Permanently remove an entire STDQC batch from the system.

    Deletes all containers whose source_id matches '<barcode_prefix>-<n>'.
    The entire batch is removed in one transaction.
    """
    # Count before deleting so we can report accurately
    count_row = db.execute(
        text("""
            SELECT COUNT(*) AS total
            FROM stdqc_container
            WHERE source_id LIKE :prefix_pattern
        """),
        {"prefix_pattern": f"{_escape_like(request.barcode_prefix)}-%"},
    ).fetchone()

    total = count_row.total if count_row else 0

    if total == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No STDQC batch found with prefix '{request.barcode_prefix}'.",
        )

    db.execute(
        text("""
            DELETE FROM stdqc_container
            WHERE source_id LIKE :prefix_pattern
        """),
        {"prefix_pattern": f"{_escape_like(request.barcode_prefix)}-%"},
    )
    db.commit()

    return {
        "barcode_prefix": request.barcode_prefix,
        "total_removed":  total,
    }
