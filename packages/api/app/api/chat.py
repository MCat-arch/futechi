"""
Route chat lanjutan. Chat SELALU terikat pada satu case, karena jawaban harus
bersandar pada graph context case tersebut (tidak ada mode chat bebas).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.case import ChatMessageOut, ChatRequest, ChatResponse
from app.services import case_service, chat_service

router = APIRouter(prefix="/cases/{case_id}/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_message(
    case_id: str, request: ChatRequest, db: AsyncSession = Depends(get_db)
):
    case = await case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(404, "case tidak ditemukan")

    try:
        assistant, scope = await chat_service.handle_chat(
            db, case=case, message=request.message
        )
    except RuntimeError as exc:
        raise HTTPException(502, f"gagal mendapat jawaban: {exc}") from exc

    return ChatResponse(
        case_id=case_id,
        reply=ChatMessageOut.model_validate(assistant),
        graph_scope=scope,
    )


@router.get("", response_model=list[ChatMessageOut])
async def list_messages(case_id: str, db: AsyncSession = Depends(get_db)):
    case = await case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(404, "case tidak ditemukan")
    return await case_service.list_chat_messages(db, case_id)
