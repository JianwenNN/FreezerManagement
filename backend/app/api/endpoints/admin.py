from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from app.database import get_db
from app import schemas

router = APIRouter()

class DrawerReservationRequest:
    drawer_id: int
    reserved: bool
    reserved_reason: Optional[str] = None

class DrawerReservationResponse:
    drawer_id: int
    freezer_asset_id: str
    layer_number: int
    rack_number: int
    drawer_number: int
    drawer_coordinate: str
    reserved: bool
    reserved_reason: Optional[str] = None

@router.post("/reserve-drawer", response_model=DrawerReservationResponse)
def reserve_drawer(
    request: DrawerReservationRequest,
    db: Session = Depends(get_db)
):
    """Admin endpoint to mark drawers as reserved or unreserved"""
    
    # Update the drawer reservation status
    result = db.execute(
        text("""
            UPDATE drawer
            SET reserved = :reserved, reserved_reason = :reason
            WHERE id = :drawer_id
            RETURNING id
        """),
        {
            "drawer_id": request.drawer_id,
            "reserved": request.reserved,
            "reason": request.reserved_reason
        }
    ).fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail="Drawer not found")
    
    # Get the updated drawer information
    drawer = db.execute(
        text("SELECT * FROM drawer_coordinates WHERE drawer_id = :drawer_id"),
        {"drawer_id": request.drawer_id}
    ).fetchone()
    
    db.commit()
    
    return {
        "drawer_id": drawer.drawer_id,
        "freezer_asset_id": drawer.freezer_asset_id,
        "layer_number": drawer.layer_number,
        "rack_number": drawer.rack_number,
        "drawer_number": drawer.drawer_number,
        "drawer_coordinate": drawer.drawer_coordinate,
        "reserved": drawer.reserved,
        "reserved_reason": drawer.reserved_reason
    }

@router.get("/reserved-drawers", response_model=List[DrawerReservationResponse])
def get_reserved_drawers(db: Session = Depends(get_db)):
    """Get all reserved drawers"""
    
    drawers = db.execute(
        text("SELECT * FROM drawer_coordinates WHERE reserved = TRUE")
    ).fetchall()
    
    return [
        {
            "drawer_id": d.drawer_id,
            "freezer_asset_id": d.freezer_asset_id,
            "layer_number": d.layer_number,
            "rack_number": d.rack_number,
            "drawer_number": d.drawer_number,
            "drawer_coordinate": d.drawer_coordinate,
            "reserved": d.reserved,
            "reserved_reason": d.reserved_reason
        }
        for d in drawers
    ]