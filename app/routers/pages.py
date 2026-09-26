import secrets
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.deps import get_current_user
from app.core.security import SECURE_COOKIES

router = APIRouter()
templates = Jinja2Templates(directory="views")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request},
    )


# ==========================================
# CATCH-ALL SPA ROUTER
# Semua URL ini hanya me-render 1 cangkang: base.html
# ==========================================
@router.get("/", response_class=HTMLResponse)
@router.get("/components", response_class=HTMLResponse)
@router.get("/vault", response_class=HTMLResponse)
@router.get("/notes", response_class=HTMLResponse)
@router.get("/ips", response_class=HTMLResponse)
@router.get("/purchases", response_class=HTMLResponse)
@router.get("/maintenance", response_class=HTMLResponse)
@router.get("/account", response_class=HTMLResponse)
@router.get("/audit", response_class=HTMLResponse)
async def render_spa_shell(request: Request, current_user=Depends(get_current_user)):
    # Mengirimkan request dan current_user ke Jinja2
    response = templates.TemplateResponse(
        request=request,
        name="base.html",
        context={
            "request": request,
            "current_user": current_user,
        },
    )
    # Pastikan cookie csrf_token tersedia untuk request mutasi HTMX
    if not request.cookies.get("csrf_token"):
        csrf_token = secrets.token_hex(16)
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,
            secure=SECURE_COOKIES,
            samesite="lax",
        )
    return response
