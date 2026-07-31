from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.core.deps import DbSession, CurrentUser
from app.models.domain import Asset, Component, NetworkIP, MaintenanceLog

router = APIRouter(tags=["Frontend Pages"])

# Mengarahkan Jinja2 ke folder views
templates = Jinja2Templates(directory="views")

# =================================================================
# PERHATIAN: Halaman /login TIDAK BOLEH menggunakan Depends(CurrentUser)
# =================================================================
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="login.html"
    )

# Halaman Dashboard WAJIB menggunakan Depends(CurrentUser)
@router.get("/", response_class=HTMLResponse)
def read_dashboard(request: Request, db: DbSession, current_user: CurrentUser):
    total_assets = db.query(Asset).count()
    total_components = db.query(Component).count()
    active_ips = db.query(NetworkIP).filter(NetworkIP.status == "Aktif").count()
    pending_maintenance = db.query(MaintenanceLog).filter(MaintenanceLog.status != "Aman").count()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "current_user": current_user,
            "total_assets": total_assets,
            "total_components": total_components,
            "active_ips": active_ips,
            "pending_maintenance": pending_maintenance
        }
    )

@router.get("/vault", response_class=HTMLResponse)
def vault_page(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(
        request=request,
        name="credentials.html",
        context={"current_user": current_user}
    )
