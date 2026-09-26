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


# ==========================================
# 3. PLACEHOLDER ENDPOINTS (Anti-404 Guard)
# Setiap menu di sidebar memiliki endpoint agar tidak 404 saat diklik.
# Masing-masing merender partial "coming soon" bawaan.
# ==========================================

def _placeholder(request: Request, current_user: CurrentUser, title: str, icon: str, desc: str):
    """Helper generik untuk merender halaman placeholder modul."""
    html = f"""
<div class="flex flex-col items-center justify-center h-full min-h-[60vh] text-center space-y-4">
    <div class="h-20 w-20 rounded-2xl bg-itam-50 text-itam-600 flex items-center justify-center text-4xl mx-auto shadow-inner">
        <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="{icon}"></path>
        </svg>
    </div>
    <h2 class="text-2xl font-extrabold text-gray-800">{title}</h2>
    <p class="text-sm text-gray-500 max-w-sm leading-relaxed">{desc}</p>
    <span class="inline-block px-3 py-1 rounded-full bg-yellow-100 text-yellow-700 text-xs font-bold uppercase tracking-wider">
        Segera Hadir
    </span>
</div>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


@router.get("/notes")
def get_notes_view(request: Request, current_user: CurrentUser):
    """Placeholder modul Catatan IT."""
    return _placeholder(
        request, current_user,
        title="Catatan IT",
        icon="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
        desc="Modul pencatatan insiden, tiket, dan catatan teknis IT. Sedang dalam pengembangan.",
    )


@router.get("/ips")
def get_ips_view(request: Request, current_user: CurrentUser):
    """Placeholder modul IP Jaringan."""
    return _placeholder(
        request, current_user,
        title="IP Jaringan",
        icon="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9",
        desc="Manajemen alokasi IP address, subnet, dan inventaris perangkat jaringan.",
    )


@router.get("/purchases")
def get_purchases_view(request: Request, current_user: CurrentUser):
    """Placeholder modul Pembelian."""
    return _placeholder(
        request, current_user,
        title="Pembelian",
        icon="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z",
        desc="Rekap nota pembelian aset IT, garansi, dan vendor management.",
    )


@router.get("/maintenance")
def get_maintenance_view(request: Request, current_user: CurrentUser):
    """Placeholder modul Maintenance."""
    return _placeholder(
        request, current_user,
        title="Maintenance",
        icon="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
        desc="Jadwal preventive maintenance, rekap perbaikan, dan history kerusakan aset.",
    )


@router.get("/account")
def get_account_view(request: Request, current_user: CurrentUser):
    """Placeholder modul Akun & Keamanan."""
    return _placeholder(
        request, current_user,
        title="Akun & Keamanan",
        icon="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z",
        desc="Manajemen pengguna, role, dan pengaturan keamanan sistem ITAM.",
    )


@router.get("/audit")
def get_audit_view(request: Request, current_user: CurrentUser):
    """Placeholder modul Audit Trail."""
    return _placeholder(
        request, current_user,
        title="Audit Trail",
        icon="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
        desc="Log seluruh aktivitas sistem: login, perubahan data, dan akses vault.",
    )
