from __future__ import annotations

from fastapi import APIRouter, Depends

from store import verify_token
from users import list_users

router = APIRouter()


@router.get("/api/users")
async def get_users(_=Depends(verify_token)):
    return list_users()
