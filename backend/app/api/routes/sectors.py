"""The staff sector view (app/services/sectors.py)."""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.db.session import get_db
from app.models import StaffUser
from app.schemas import SectorSummaryOut
from app.services.sectors import sector_summaries

router = APIRouter()


@router.get("/api/sectors", response_model=List[SectorSummaryOut])
async def sectors(db: Session = Depends(get_db), _: StaffUser = Depends(require_staff)):
    """Every sector with its households, held readings, possible leaks and money owed; the
    sectors that need attention first."""
    return sector_summaries(db)
