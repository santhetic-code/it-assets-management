import secrets
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.deps import CurrentUser, DbSession
from app.core.limiter import limiter
from app.core.security import SECURE_COOKIES, create_access_token, verify_jwt_token
from app.models import domain
from app.models.schemas.user import UserCreate
from app.services import (
    asset_service,
    auth_service,
    component_service,
    ip_service,
    vault_service,
)

router = APIRouter(tags=["Frontend Pages"])
templates = Jinja2Templates(directory="views")


def render_template(request: Request, name: str, context: dict = None):
    """
    Helper untuk merender template Jinja2 sekaligus memastikan
    csrf_token diterbitkan, dimasukkan ke context template, dan disimpan di cookie browser.
    Serta menambahkan header Cache-Control agar browser selalu mengambil HTML terbaru secara real-time.
    """
    if context is None:
        context = {}
    csrf_token = request.cookies.get("csrf_token") or secrets.token_hex(16)
    context["csrf_token"] = csrf_token
    response = templates.TemplateResponse(request=request, name=name, context=context)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=SECURE_COOKIES,
        samesite="lax",
    )
    # Hancurkan cache browser agar halaman HTML selalu fresh dari server
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ==========================================
# 1. AUTENTIKASI (LOGIN & LOGOUT)
# ==========================================
@router.get("/login")
def login_page(request: Request):
    token = request.cookies.get("itam_session")
    if token:
        try:
            verify_jwt_token(token)
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        except Exception:
            pass
    return render_template(request=request, name="login.html")


@router.post("/login")
@limiter.limit("5/minute")
def login_submit(
    request: Request,
    db: DbSession,
    username: str = Form(...),
    password: str = Form(...),
):
    # 1. Validasi kredensial pengguna via auth_service
    user = auth_service.authenticate_user(db, username, password)

    # 2. Jika gagal: render ulang login.html dengan pesan error (200 OK)
    if not user:
        return render_template(
            request=request,
            name="login.html",
            context={
                "error_msg": "Username atau Password salah!",
                "error": "Username atau Password salah!",
            },
        )

    # 3. Jika berhasil: buat RedirectResponse ke Dashboard (302)
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    # 4. Set radar online & Cookie Sesi JWT aman
    user.is_online = True
    db.commit()

    access_token = create_access_token(
        data={"sub": user.username}
    )
    response.set_cookie(
        key="itam_session",
        value=access_token,
        httponly=True,
        secure=SECURE_COOKIES,  # True di production (HTTPS), False di development (HTTP)
        samesite="lax",
        max_age=120 * 60,
    )
    return response


@router.get("/logout")
def logout_action(request: Request, db: DbSession):
    token = request.cookies.get("access_token") or request.cookies.get("itam_session")
    if token:
        try:
            payload = verify_jwt_token(token)
            sub = payload.get("sub")
            if str(sub).isdigit():
                u = db.query(domain.User).filter(domain.User.id == int(sub)).first()
            else:
                u = db.query(domain.User).filter(domain.User.username == sub).first()
            if u:
                u.is_online = False
                db.commit()
        except Exception:
            pass
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    response.delete_cookie("itam_session")
    return response


# ==========================================
# 2. DASHBOARD UTAMA
# ==========================================
@router.get("/")
def read_dashboard(request: Request, db: DbSession, current_user: CurrentUser):
    return render_template(
        request=request,
        name="base.html",
        context={"current_user": current_user},
    )


# ==========================================
# 3. HALAMAN MENU LAINNYA
# ==========================================
@router.get("/it-notes")
def read_it_notes(request: Request, db: DbSession, current_user: CurrentUser):
    # Mengambil data aset aktif dari MySQL
    assets = db.query(domain.Asset).filter(domain.Asset.is_deleted == False).all()
    # Mengirimkan variabel 'assets' ke Jinja2
    return render_template(
        request=request,
        name="it_notes.html",
        context={"current_user": current_user, "assets": assets},
    )


@router.get("/network")
def read_network(request: Request, db: DbSession, current_user: CurrentUser):
    ips = ip_service.get_all_ips(db)
    count_aktif = db.query(domain.NetworkIP).filter(domain.NetworkIP.status == "Aktif").count()
    count_offline = db.query(domain.NetworkIP).filter(domain.NetworkIP.status == "Offline").count()
    count_tersedia = max(0, 254 - (count_aktif + count_offline))
    return render_template(
        request=request,
        name="ips.html",
        context={
            "current_user": current_user,
            "ips": ips,
            "count_aktif": count_aktif,
            "count_offline": count_offline,
            "count_tersedia": count_tersedia,
        },
    )


@router.get("/vault")
def read_vault(request: Request, db: DbSession, current_user: CurrentUser):
    # Mengambil semua data vault dari database
    vaults = db.query(domain.Vault).all()
    return render_template(
        request=request,
        name="credentials.html",
        context={"current_user": current_user, "vaults": vaults},
    )


@router.get("/purchase-records")
def read_purchases(request: Request, db: DbSession, current_user: CurrentUser):
    purchases = asset_service.get_purchases(db)
    assets = asset_service.get_all_assets(db)
    return render_template(
        request=request,
        name="purchases.html",
        context={
            "current_user": current_user,
            "purchases": purchases,
            "assets": assets,
        },
    )


@router.get("/hardware-components")
@router.get("/components")
def read_components(request: Request, db: DbSession, current_user: CurrentUser):
    return render_template(
        request=request,
        name="base.html",
        context={"current_user": current_user},
    )


@router.get("/maintenance-logs")
def read_maintenance(request: Request, db: DbSession, current_user: CurrentUser):
    maintenance_logs = asset_service.get_all_maintenance(db)
    assets = asset_service.get_all_assets(db)
    return render_template(
        request=request,
        name="maintenance.html",
        context={
            "current_user": current_user,
            "maintenance_logs": maintenance_logs,
            "assets": assets,
        },
    )


@router.get("/account")
def read_account(request: Request, db: DbSession, current_user: CurrentUser):
    users = auth_service.get_all_users(db)
    return render_template(
        request=request,
        name="account.html",
        context={
            "current_user": current_user,
            "users": users,
            "error_msg": request.query_params.get("error"),
            "success_msg": request.query_params.get("success"),
        },
    )


@router.get("/system-logs")
def read_logs(request: Request, db: DbSession, current_user: CurrentUser):
    logs = (
        db.query(domain.SystemLogs)
        .order_by(domain.SystemLogs.timestamp.desc())
        .limit(100)
        .all()
    )
    return render_template(
        request=request,
        name="logs.html",
        context={"current_user": current_user, "logs": logs},
    )


# ==========================================
# 4. ENDPOINT AKSI FORM
# ==========================================
@router.post("/add-user")
def handle_add_user(
    request: Request,
    db: DbSession,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    csrf_token: str = Form(...),
):
    # 1. Validasi CSRF Token untuk keamanan
    cookie_csrf = request.cookies.get("csrf_token")
    if not cookie_csrf or cookie_csrf != csrf_token:
        return RedirectResponse(
            url="/account?error=csrf_invalid", status_code=status.HTTP_303_SEE_OTHER
        )

    # 2. Buat user melalui auth_service
    try:
        user_in = UserCreate(username=username, password=password, role=role)
        auth_service.create_user(db, user_in)
        return RedirectResponse(
            url="/account?success=user_added", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception:
        return RedirectResponse(
            url="/account?error=duplicate_user", status_code=status.HTTP_303_SEE_OTHER
        )
