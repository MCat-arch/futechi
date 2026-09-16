"""
Route cage: status monitoring, "Tandai Sembuh", dan "Reset Monitoring Cage".

Keduanya SENGAJA manual (tidak otomatis dari waktu): masa penyembuhan penyakit
unggas bervariasi, dan ayam bisa diganti/dipindah di tengah masa exclusion.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from futechi_graphrag.domain.value_objects.enums import CageStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.case import Cage
from app.schemas.case import CageOut
from app.services import case_service

router = APIRouter(prefix="/cages", tags=["cages"])


@router.get("", response_model=list[CageOut])
async def list_cages(
    status: CageStatus | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Cage).order_by(Cage.updated_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Cage.status == status)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/{cage_id}", response_model=CageOut)
async def get_cage(cage_id: str, db: AsyncSession = Depends(get_db)):
    cage = await db.get(Cage, cage_id)
    if not cage:
        raise HTTPException(404, "cage tidak ditemukan")
    return cage


@router.post("/{cage_id}/recover", response_model=CageOut)
async def mark_recovered(cage_id: str, db: AsyncSession = Depends(get_db)):
    """Tandai Sembuh: cage keluar dari EXCLUDED_SICK dan bisa dialert lagi."""
    cage = await case_service.release_cage(db, cage_id)
    if not cage:
        raise HTTPException(404, "cage tidak ditemukan")
    return cage


@router.post("/{cage_id}/reset", response_model=CageOut)
async def reset_monitoring(cage_id: str, db: AsyncSession = Depends(get_db)):
    """Reset Monitoring: dipakai saat ayam diganti/dipindah di tengah exclusion."""
    cage = await case_service.release_cage(db, cage_id)
    if not cage:
        raise HTTPException(404, "cage tidak ditemukan")
    return cage
