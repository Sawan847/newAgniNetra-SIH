"""Authentication and User Management API endpoints."""

from __future__ import annotations

import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import TokenResponse, UserCreateRequest, UserLoginRequest, UserRead
from app.services.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    require_role,
    seed_default_admin,
    verify_password,
)

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with email and password",
)
def login(credentials: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate platform user and return JWT bearer token."""
    # Auto-seed default admin if database is initialized without users
    user = db.scalar(select(User).where(User.email == credentials.email))
    if not user and credentials.email == "admin@agnietra.gov.in":
        user = seed_default_admin(db)

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated",
        )

    user.last_login = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserRead.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get profile of currently authenticated user",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Return identity and roles for the active session."""
    return UserRead.model_validate(current_user)


@router.post(
    "/register",
    response_model=UserRead,
    summary="Create a new user account (Admin only)",
)
def register_user(
    req: UserCreateRequest,
    current_admin: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to provision analyst and operator accounts."""
    existing = db.scalar(select(User).where(User.email == req.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{req.email}' already exists",
        )

    new_user = User(
        id=uuid.uuid4(),
        email=req.email,
        hashed_password=get_password_hash(req.password),
        full_name=req.full_name,
        role=req.role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserRead.model_validate(new_user)
