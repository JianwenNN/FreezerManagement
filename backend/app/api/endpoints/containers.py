from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app import schemas

router = APIRouter()

@router.post("/allocate-proximity/", response_model=List[schemas.DrawerAllocation])
def allocate_containers_in_proximity(
    request: schemas.ContainerAllocationRequest,
    db: Session = Depends(get_db)
):
    """Allocate space for multiple containers in nearby drawers"""
    
    query = text("""
        SELECT * FROM allocate_containers_in_proximity(
            :container_type_id, :container_count
        )
    """)
    
    results = db.execute(
        query,
        {
            "container_type_id": request.container_type_id,
            "container_count": request.number_of_containers
        }
    ).fetchall()
    
    if not results:
        raise HTTPException(
            status_code=400,
            detail="Not enough space available for the requested containers"
        )
    
    total_allocated = sum(row.container_count for row in results)
    if total_allocated < request.number_of_containers:
        raise HTTPException(
            status_code=400,
            detail=f"Only space for {total_allocated} containers found, but {request.number_of_containers} were requested"
        )
    
    # Convert to response format
    allocations = []
    for row in results:
        # Get detailed drawer information
        drawer = db.execute(
            text("SELECT * FROM drawer_coordinates WHERE drawer_id = :drawer_id"),
            {"drawer_id": row.drawer_id}
        ).fetchone()
        
        allocations.append({
            "drawer_id": row.drawer_id,
            "freezer_asset_id": drawer.freezer_asset_id,
            "layer_number": drawer.layer_number,
            "rack_number": drawer.rack_number,
            "drawer_number": drawer.drawer_number,
            "drawer_coordinate": drawer.drawer_coordinate,
            "container_count": row.container_count
        })
    
    return allocations