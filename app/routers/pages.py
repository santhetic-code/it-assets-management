from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.deps import DbSession, CurrentUser
from app.services import auth_service
from app.core.security import create_access_token, SECURE_COOKIES

router = APIRouter(tags=["Frontend Pages"])
templates = Jinja2Templates(directory="views")

# ==========================================
# 1. AUTENTIKASI (LOGIN & LOGOUT)
# ==========================================
@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@router.post("/login")
def login_submit(
    request: Request,
    db: DbSession,
    username: str = Form(...),
    password: str = Form(...)
):
    user = auth_service.authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Username atau password salah!"}
        )
    
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="itam_session",
        value=access_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="lax",
        max_age=120 * 60
    )
    return response

@router.get("/logout")
def logout_action():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("itam_session")
    return response


# ==========================================
# 2. DASHBOARD UTAMA
# ==========================================
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
            "pending_maintenance": 0,
            "status_labels": ["Aman", "Perlu Dicek", "Kritis"],
            "status_data": [0, 0, 0],
            "condition_labels": ["Bagus", "Rusak Ringan", "Rusak Berat"],
            "condition_data": [0, 0, 0],
            "bar_labels": ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun"],
            "bar_data": [0, 0, 0, 0, 0, 0],
            "pie_labels": ["Tersedia", "Dipinjam", "Rusak"],
            "pie_data": [0, 0, 0]
        }
    )


# ==========================================
# 3. HALAMAN MENU LAINNYA
# ==========================================
@router.get("/it-notes")
def read_it_notes(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(request=request, name="it_notes.html", context={"current_user": current_user})

@router.get("/network")
def read_network(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(request=request, name="ips.html", context={"current_user": current_user})

@router.get("/vault")
def read_vault(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(request=request, name="credentials.html", context={"current_user": current_user})

@router.get("/purchase-records")
def read_purchases(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(request=request, name="purchases.html", context={"current_user": current_user})

@router.get("/hardware-components")
def read_components(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(request=request, name="components.html", context={"current_user": current_user})

@router.get("/maintenance-logs")
def read_maintenance(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(request=request, name="maintenance.html", context={"current_user": current_user})

@router.get("/account")
def read_account(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(request=request, name="account.html", context={"current_user": current_user})

@router.get("/system-logs")
def read_logs(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(request=request, name="logs.html", context={"current_user": current_user})