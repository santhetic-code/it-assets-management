from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, Response
from pydantic import BaseModel

from app.core.deps import DbSession, CurrentUser, require_super_admin, get_audit_logger
from app.models.schemas.user import UserResponse, UserCreate, UserUpdate
from app.services import auth_service
from app.core.security import create_access_token, SECURE_COOKIES

router = APIRouter(prefix="/api/auth", tags=["Auth & Users"])

class LoginRequest(BaseModel):
    username: str
    password: str

# 1. LOGIN & LOGOUT API
@router.post("/login")
def login(request_data: LoginRequest, response: Response, db: DbSession):
    user = auth_service.authenticate_user(db, request_data.username, request_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah.")
    
    # Buat JWT Token
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    
    # Set Cookie Sesi (Otomatis Secure=True jika di production)
    response.set_cookie(
        key="itam_session",
        value=access_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="lax",
        max_age=120 * 60 # 120 Menit
    )
    return {"message": "Login berhasil", "role": user.role}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("itam_session")
    return {"message": "Logout berhasil"}


# 2. USER MANAGEMENT (KHUSUS SUPER ADMIN)
@router.get("/users", response_model=List[UserResponse], dependencies=[Depends(require_super_admin)])
def read_users(db: DbSession):
    return auth_service.get_all_users(db)

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_super_admin), Depends(get_audit_logger)])
def create_user(user_data: UserCreate, db: DbSession):
    return auth_service.create_user(db, user_data)

@router.put("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(require_super_admin), Depends(get_audit_logger)])
def update_user(user_id: int, user_data: UserUpdate, db: DbSession):
    return auth_service.update_user(db, user_id, user_data)

@router.delete("/users/{user_id}", dependencies=[Depends(require_super_admin), Depends(get_audit_logger)])
def delete_user(user_id: int, current_user: CurrentUser, db: DbSession):
    return auth_service.delete_user(db, user_id, current_user.id)
