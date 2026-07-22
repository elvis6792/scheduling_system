from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.domain import User
from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.database import get_session
from app.core.dependencies import get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/auth/login")
async def login(request: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="帳號或密碼錯誤",
        )

    access_token = create_access_token(data={"sub": user.username, "role": user.role, "user_id": user.id, "staff_id": user.staff_id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
        "staff_id": user.staff_id
    }


class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, description="新密碼長度至少需 8 碼")
    confirm_password: str

@router.put("/users/me/password")
async def update_user_password(
    payload: PasswordUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密碼與確認密碼不一致。"
        )

    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="舊密碼驗證失敗。"
        )

    if payload.old_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密碼不可與舊密碼相同。"
        )

    current_user.hashed_password = get_password_hash(payload.new_password)
    session.add(current_user)
    await session.commit()
    
    return {"message": "密碼修改成功"}
