import json
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, DbSession, get_current_user
from app.core.security import SECURE_COOKIES, verify_csrf_token
from app.models.schemas.component import ComponentCreate, ComponentUpdate
from app.services import asset_service, component_service

router = APIRouter(prefix="/ui", tags=["UI HTMX"])
templates = Jinja2Templates(directory="views")


def render_template(request: Request, name: str, context: Optional[dict] = None) -> Response:
    """Helper Jinja2 render untuk fragmen DOM HTMX dengan perlindungan CSRF."""
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
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    return response


# ==========================================
# 1. HARDWARE & PC (KOMPONEN) ENDPOINTS
# ==========================================

@router.get("/components")
def get_components_view(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
):
    """Merender tampilan utama modul Hardware & PC (Stat Cards + Toolbar + Tabel)."""
    components = component_service.get_components(db)
    stats = component_service.get_component_stats(db)
    return render_template(
        request=request,
        name="partials/components.html",
        context={
            "components": components,
            "stats": stats,
            "current_user": current_user,
        },
    )


@router.get("/components/table")
def get_components_table_view(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = None,
    category: Optional[str] = None,
    type: Optional[str] = None,
    type_filter: Optional[str] = None,
):
    """Merender tabel komponen secara responsif berdasarkan filter dan kata kunci."""
    selected_category = type or type_filter or category
    components = component_service.get_components_filtered(db, search=search, category=selected_category)
    return render_template(
        request=request,
        name="partials/components_table.html",
        context={
            "components": components,
            "current_user": current_user,
            "selected_type": selected_category,
            "search": search,
        },
    )


@router.get("/components/modal/add")
def get_add_component_modal(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
):
    """Merender modal tambah PC dengan dropdown Master Component (Single Source of Truth)."""
    masters = component_service.get_master_components_grouped(db)
    assets = asset_service.get_all_assets(db)
    return render_template(
        request=request,
        name="partials/component_form_modal.html",
        context={
            "is_edit": False,
            "component": None,
            "masters": masters,
            "assets": assets,
            "current_user": current_user,
        },
    )


@router.get("/components/{component_id}/modal/edit")
def get_edit_component_modal(
    request: Request,
    component_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Merender modal edit PC dengan data terisi dan input alasan perubahan."""
    comp = component_service.get_component(db, component_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Spesifikasi PC tidak ditemukan")
    
    masters = component_service.get_master_components_grouped(db)
    assets = asset_service.get_all_assets(db)
    return render_template(
        request=request,
        name="partials/component_form_modal.html",
        context={
            "is_edit": True,
            "component": comp,
            "masters": masters,
            "assets": assets,
            "current_user": current_user,
        },
    )


@router.post("/components/create", dependencies=[Depends(verify_csrf_token)])
def create_component_action(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    name: str = Form(...),
    pc_type: str = Form("Operasional"),
    asset_id: Optional[int] = Form(None),
    cpu_id: Optional[int] = Form(None),
    ram_id: Optional[int] = Form(None),
    storage_id: Optional[int] = Form(None),
    mainboard_id: Optional[int] = Form(None),
    vga_id: Optional[int] = Form(None),
    os_id: Optional[int] = Form(None),
    monitor_id: Optional[int] = Form(None),
    keyboard: Optional[str] = Form(None),
    mouse: Optional[str] = Form(None),
    psu: Optional[str] = Form(None),
    casing: Optional[str] = Form(None),
):
    """Membuat spesifikasi PC baru dengan validasi foreign key ketat."""
    component_in = ComponentCreate(
        name=name,
        pc_type=pc_type,
        asset_id=asset_id,
        cpu_id=cpu_id,
        ram_id=ram_id,
        storage_id=storage_id,
        mainboard_id=mainboard_id,
        vga_id=vga_id,
        os_id=os_id,
        monitor_id=monitor_id,
        keyboard=keyboard,
        mouse=mouse,
        psu=psu,
        casing=casing,
    )
    new_comp = component_service.create_component(db, component_in, current_user_id=current_user.id)

    # Render ulang tampilan modul utama dengan toast notifikasi
    components = component_service.get_components(db)
    stats = component_service.get_component_stats(db)
    response = render_template(
        request=request,
        name="partials/components.html",
        context={
            "components": components,
            "stats": stats,
            "current_user": current_user,
        },
    )
    toast_payload = {
        "title": "Berhasil Didaftarkan",
        "message": f"Spesifikasi PC '{new_comp.name}' berhasil disimpan.",
        "type": "success",
    }
    response.headers["HX-Trigger"] = json.dumps({"showToast": toast_payload})
    return response


@router.post("/components/{component_id}/update", dependencies=[Depends(verify_csrf_token)])
def update_component_action(
    request: Request,
    component_id: int,
    db: DbSession,
    current_user: CurrentUser,
    name: str = Form(...),
    pc_type: str = Form("Operasional"),
    asset_id: Optional[int] = Form(None),
    cpu_id: Optional[int] = Form(None),
    ram_id: Optional[int] = Form(None),
    storage_id: Optional[int] = Form(None),
    mainboard_id: Optional[int] = Form(None),
    vga_id: Optional[int] = Form(None),
    os_id: Optional[int] = Form(None),
    monitor_id: Optional[int] = Form(None),
    keyboard: Optional[str] = Form(None),
    mouse: Optional[str] = Form(None),
    psu: Optional[str] = Form(None),
    casing: Optional[str] = Form(None),
    update_reason: Optional[str] = Form(None),
):
    """Memperbarui spesifikasi PC dan mencatat audit trail perubahannya."""
    component_update = ComponentUpdate(
        name=name,
        pc_type=pc_type,
        asset_id=asset_id,
        cpu_id=cpu_id,
        ram_id=ram_id,
        storage_id=storage_id,
        mainboard_id=mainboard_id,
        vga_id=vga_id,
        os_id=os_id,
        monitor_id=monitor_id,
        keyboard=keyboard,
        mouse=mouse,
        psu=psu,
        casing=casing,
        update_reason=update_reason or "Update spesifikasi rutin",
    )
    updated_comp = component_service.update_component(
        db, component_id=component_id, component_data=component_update, current_user_id=current_user.id
    )
    if not updated_comp:
        raise HTTPException(status_code=404, detail="Spesifikasi PC tidak ditemukan")

    # Render ulang modul utama
    components = component_service.get_components(db)
    stats = component_service.get_component_stats(db)
    response = render_template(
        request=request,
        name="partials/components.html",
        context={
            "components": components,
            "stats": stats,
            "current_user": current_user,
        },
    )
    toast_payload = {
        "title": "Perubahan Tersimpan",
        "message": f"Spesifikasi PC '{updated_comp.name}' berhasil diperbarui.",
        "type": "success",
    }
    response.headers["HX-Trigger"] = json.dumps({"showToast": toast_payload})
    return response


@router.delete("/components/{component_id}", dependencies=[Depends(verify_csrf_token)])
def delete_component_action(
    request: Request,
    component_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Menonaktifkan spesifikasi PC (Soft Delete) dan merekam audit log."""
    deleted_comp = component_service.delete_component(db, component_id=component_id, current_user_id=current_user.id)
    if not deleted_comp:
        raise HTTPException(status_code=404, detail="Spesifikasi PC tidak ditemukan")

    components = component_service.get_components(db)
    stats = component_service.get_component_stats(db)
    response = render_template(
        request=request,
        name="partials/components.html",
        context={
            "components": components,
            "stats": stats,
            "current_user": current_user,
        },
    )
    toast_payload = {
        "title": "PC Dinonaktifkan",
        "message": f"Spesifikasi PC '{deleted_comp.name}' berhasil dinonaktifkan.",
        "type": "warning",
    }
    response.headers["HX-Trigger"] = json.dumps({"showToast": toast_payload})
    return response


@router.get("/components/{component_id}/history")
def get_component_history_view(
    request: Request,
    component_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Merender timeline riwayat perubahan (Audit Trail) dari spesifikasi PC."""
    comp = component_service.get_component(db, component_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Spesifikasi PC tidak ditemukan")
    history = component_service.get_component_history(db, component_id)
    return render_template(
        request=request,
        name="partials/component_history_modal.html",
        context={
            "component": comp,
            "history": history,
            "current_user": current_user,
        },
    )


# ==========================================
# 2. DASHBOARD & VAULT PLACEHOLDER ENDPOINTS
# ==========================================

@router.get("/dashboard")
def get_dashboard_view(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
):
    """Merender tampilan ringkasan Dashboard dalam format HTMX partial."""
    stats = asset_service.get_dashboard_stats(db)
    return render_template(
        request=request,
        name="partials/dashboard.html",
        context={
            "current_user": current_user,
            **stats,
        },
    )


@router.get("/vault")
def get_vault_view(
    request: Request,
    current_user: CurrentUser,
):
    """Merender tampilan pratinjau Kredensial Vault (siap dieksekusi berikutnya)."""
    return render_template(
        request=request,
        name="partials/vault.html",
        context={"current_user": current_user},
    )
