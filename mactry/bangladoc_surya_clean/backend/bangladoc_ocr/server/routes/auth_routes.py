from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bangladoc_ocr.auth import (
    create_access_token,
    find_user_by_email,
    get_current_user,
    hash_password,
    verify_password,
)
from bangladoc_ocr.db.models import User
from bangladoc_ocr.db.session import get_db
from bangladoc_ocr.schemas import LoginPayload, RegisterPayload, TokenResponse, UserResponse

router = APIRouter()


@router.post("/auth/register", response_model=UserResponse)
async def auth_register(payload: RegisterPayload, db: AsyncSession = Depends(get_db)) -> UserResponse:
    existing = await find_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=payload.email.lower().strip(), hashed_password=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/auth/login", response_model=TokenResponse)
async def auth_login(payload: LoginPayload, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await find_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user_id=user.id, role=user.role.value)


@router.get("/auth/me", response_model=UserResponse)
async def auth_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
