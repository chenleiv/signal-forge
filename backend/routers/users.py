from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from authz import check_user_create, check_user_delete, check_user_update, require_admin
from database import get_db
from store import verify_token
from user_admin import create_user, delete_user, update_user
from users import CurrentUser, get_user_record, list_users, user_directory

router = APIRouter()


@router.get("/api/users")
async def get_users(_=Depends(verify_token)):
    """Active users (assignable). Never includes password hashes."""
    return list_users()


@router.get("/api/users/directory")
async def get_user_directory(_=Depends(verify_token)):
    """Every name ever used, including deleted users, so history keeps names."""
    return user_directory()


@router.post("/api/users", status_code=201)
async def post_user(body: dict, db: Optional[AsyncSession] = Depends(get_db), _=Depends(require_admin)):
    check_user_create(body)
    return await create_user(db, body)


@router.patch("/api/users/{username}")
async def patch_user(username: str, body: dict, db: Optional[AsyncSession] = Depends(get_db),
                     actor: CurrentUser = Depends(verify_token)):
    # Admins change role/password of anyone; managers only reset analysts' passwords.
    check_user_update(actor, get_user_record(username), body)
    return await update_user(db, username, body)


@router.delete("/api/users/{username}")
async def remove_user(username: str, db: Optional[AsyncSession] = Depends(get_db),
                      admin: CurrentUser = Depends(require_admin)):
    check_user_delete(get_user_record(username))
    await delete_user(db, admin, username)
    return {"ok": True}
