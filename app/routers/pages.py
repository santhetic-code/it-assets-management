from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.deps import DbSession, CurrentUser
from app.services import auth_service
from app.core.security import create_access_token, SECURE_COOKIES

router = APIRouter(tags=["Frontend Pages"])
templates = Jinja2Templates(directory="views")

# 1. Menampilkan Halaman Login
@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="login.html"
    )

# 2. Menerima Submit Formulir dari HTML Lama
@router.post("/login")
def login_submit(
    request: Request,
    db: DbSession,
    username: str = Form(...),
    password: str = Form(...)
):
    user = auth_service.authenticate_user(db, username, password)
    
    if not user:
        # Jika gagal, kembalikan ke halaman login dengan pesan error
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Username atau password salah!"}
        )
    
    # Jika sukses, buat token JWT
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    
    # Buat respon pengalihan (Redirect) ke halaman utama ("/")
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    # Tanamkan token ke dalam Cookie
    response.set_cookie(
        key="itam_session",
        value=access_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="lax",
        max_age=120 * 60
    )
    return response

# 3. Menangani Tombol Logout dari HTML
@router.get("/logout")
def logout_action():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("itam_session")
    return response

# 4. Menampilkan Dashboard (Hanya bisa diakses jika sudah ada Cookie)
@router.get("/")
def read_dashboard(request: Request, db: DbSession, current_user: CurrentUser):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "current_user": current_user,
            "total_assets": 0,
            "total_components": 0,
            "active_ips": 0,
            "pending_maintenance": 0
        }
    )
