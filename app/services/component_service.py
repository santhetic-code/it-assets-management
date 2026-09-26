from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import exc, or_, func
from typing import List, Optional
from app.models.domain import Component, ComponentHistory, MasterComponent, Asset
from app.models.schemas.component import ComponentCreate, ComponentUpdate


def get_utc_now():
    return datetime.now(timezone.utc)


def get_components(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(Component)
        .options(
            joinedload(Component.cpu_ref),
            joinedload(Component.ram_ref),
            joinedload(Component.storage_ref),
            joinedload(Component.mainboard_ref),
            joinedload(Component.os_ref),
            joinedload(Component.vga_ref),
            joinedload(Component.monitor_ref),
            joinedload(Component.asset),
        )
        .filter(Component.is_deleted == False)
        .order_by(Component.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_components_filtered(db: Session, search: Optional[str] = None, category: Optional[str] = None):
    query = (
        db.query(Component)
        .options(
            joinedload(Component.cpu_ref),
            joinedload(Component.ram_ref),
            joinedload(Component.storage_ref),
            joinedload(Component.mainboard_ref),
            joinedload(Component.os_ref),
            joinedload(Component.vga_ref),
            joinedload(Component.monitor_ref),
            joinedload(Component.asset),
        )
        .filter(Component.is_deleted == False)
    )

    if category and category.strip() and category != "Semua":
        query = query.filter(Component.pc_type == category.strip())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Component.name.ilike(term),
                Component.pc_type.ilike(term),
                Component.processor_spec.ilike(term),
                Component.ram_spec.ilike(term),
                Component.storage_spec.ilike(term),
                Component.mainboard_spec.ilike(term),
                Component.vga_spec.ilike(term),
                Component.os_name.ilike(term),
                Component.monitor.ilike(term),
                Component.keyboard.ilike(term),
                Component.mouse.ilike(term),
                Component.psu.ilike(term),
                Component.casing.ilike(term),
            )
        )

    return query.order_by(Component.id.desc()).all()


def get_master_components(db: Session, category: Optional[str] = None) -> List[MasterComponent]:
    query = db.query(MasterComponent)
    if category:
        query = query.filter(MasterComponent.category == category)
    return query.order_by(MasterComponent.name.asc()).all()


def get_master_components_grouped(db: Session) -> dict:
    masters = db.query(MasterComponent).order_by(MasterComponent.name.asc()).all()
    grouped = {}
    for m in masters:
        cat = (m.category or "OTHER").strip().upper()
        grouped.setdefault(cat, []).append(m)
    return grouped



def get_component_stats(db: Session) -> dict:
    """Mengembalikan hitungan PC per kategori langsung dari database."""
    total_all = db.query(func.count(Component.id)).filter(Component.is_deleted == False).scalar() or 0
    total_operasional = db.query(func.count(Component.id)).filter(
        Component.is_deleted == False, Component.pc_type == "Operasional"
    ).scalar() or 0
    total_server = db.query(func.count(Component.id)).filter(
        Component.is_deleted == False, Component.pc_type == "Server"
    ).scalar() or 0
    total_backup = db.query(func.count(Component.id)).filter(
        Component.is_deleted == False, Component.pc_type == "Backup"
    ).scalar() or 0
    return {
        "total_all": total_all,
        "total_operasional": total_operasional,
        "total_server": total_server,
        "total_backup": total_backup,
    }



def get_component(db: Session, component_id: int):
    return (
        db.query(Component)
        .options(
            joinedload(Component.cpu_ref),
            joinedload(Component.ram_ref),
            joinedload(Component.storage_ref),
            joinedload(Component.mainboard_ref),
            joinedload(Component.os_ref),
            joinedload(Component.vga_ref),
            joinedload(Component.monitor_ref),
            joinedload(Component.asset),
        )
        .filter(Component.id == component_id, Component.is_deleted == False)
        .first()
    )



def create_component(db: Session, component: ComponentCreate, current_user_id: int):
    db_component = Component(
        name=component.name,
        pc_type=component.pc_type,
        asset_id=component.asset_id,
        processor_spec=component.processor_spec,
        ram_spec=component.ram_spec,
        storage_spec=component.storage_spec,
        mainboard_spec=component.mainboard_spec,
        vga_spec=component.vga_spec,
        os_name=component.os_name,
        monitor=component.monitor,
        os_id=component.os_id,
        cpu_id=component.cpu_id,
        mainboard_id=component.mainboard_id,
        ram_id=component.ram_id,
        vga_id=component.vga_id,
        storage_id=component.storage_id,
        monitor_id=component.monitor_id,
        keyboard=component.keyboard,
        mouse=component.mouse,
        psu=component.psu,
        casing=component.casing,
        created_at=get_utc_now(),
        updated_at=get_utc_now()
    )
    
    db.add(db_component)
    db.commit()
    db.refresh(db_component)

    # REFAKTOR: Catat JSON ke History
    history_entry = ComponentHistory(
        component_id=db_component.id,
        user_id=current_user_id,
        action_type="CREATE",
        changes_detail={
            "reason": "Pendaftaran awal spesifikasi PC",
            "changes": []
        },
        created_at=get_utc_now()
    )
    db.add(history_entry)
    db.commit()

    return db_component


def update_component(db: Session, component_id: int, component_data: ComponentUpdate, current_user_id: int):
    db_comp = get_component(db, component_id)
    if not db_comp:
        return None

    old_state = {
        "name": db_comp.name,
        "pc_type": db_comp.pc_type,
        "processor_spec": db_comp.processor_spec,
        "ram_spec": db_comp.ram_spec,
        "storage_spec": db_comp.storage_spec,
        "mainboard_spec": db_comp.mainboard_spec,
        "vga_spec": db_comp.vga_spec,
        "os_name": db_comp.os_name,
        "monitor": db_comp.monitor,
        "os_id": db_comp.os_id,
        "cpu_id": db_comp.cpu_id,
        "mainboard_id": db_comp.mainboard_id,
        "ram_id": db_comp.ram_id,
        "vga_id": db_comp.vga_id,
        "storage_id": db_comp.storage_id,
        "monitor_id": db_comp.monitor_id,
        "keyboard": db_comp.keyboard,
        "mouse": db_comp.mouse,
        "psu": db_comp.psu,
        "casing": db_comp.casing
    }

    update_data = component_data.model_dump(exclude_unset=True)
    update_reason = update_data.pop("update_reason", None)

    for key, value in update_data.items():
        setattr(db_comp, key, value)
    
    db_comp.updated_at = get_utc_now()
    db.commit()
    db.refresh(db_comp)

    # REFAKTOR: Bangun JSON Array untuk perubahan
    changes = []
    for key, old_val in old_state.items():
        new_val = getattr(db_comp, key)
        if str(old_val) != str(new_val):
            changes.append({
                "field": key,
                "old_value": old_val,
                "new_value": new_val
            })

    if changes:
        action_type = "UPDATE"
        # Cek apakah ada perubahan di sektor kritikal
        if any(c["field"] in ["ram_id", "storage_id", "cpu_id"] for c in changes):
            action_type = "UPGRADE/DOWNGRADE"

        history_entry = ComponentHistory(
            component_id=db_comp.id,
            user_id=current_user_id,
            action_type=action_type,
            changes_detail={
                "reason": update_reason or "Update spesifikasi rutin",
                "changes": changes
            },
            created_at=get_utc_now()
        )
        db.add(history_entry)
        db.commit()

    return db_comp


def delete_component(db: Session, component_id: int, current_user_id: int):
    db_comp = get_component(db, component_id)
    if db_comp:
        db_comp.is_deleted = True
        db_comp.deleted_at = get_utc_now()
        db_comp.deleted_by = current_user_id
        
        # REFAKTOR: Catat JSON ke History
        history = ComponentHistory(
            component_id=db_comp.id,
            user_id=current_user_id,
            action_type="DECOMMISSION",
            changes_detail={
                "reason": "Penghapusan komponen (Soft Delete)",
                "changes": [{"field": "is_deleted", "old_value": False, "new_value": True}]
            },
            created_at=get_utc_now()
        )
        db.add(history)
        db.commit()
    return db_comp


def get_component_history(db: Session, component_id: int):
    return db.query(ComponentHistory).filter(ComponentHistory.component_id == component_id).order_by(ComponentHistory.created_at.desc()).all()


# Helper untuk kompatibilitas modul lain (pages & asset_service)
def soft_delete_component(db: Session, component_id: int, user_id: int | None = None, client_ip: str | None = None):
    return delete_component(db, component_id, current_user_id=user_id)


# CATATAN PERBAIKAN:
# Sebelumnya ada 2 fungsi `get_component_stats` di file ini (definisi kedua otomatis
# menimpa yang pertama di Python). Definisi kedua mengembalikan key "count_total",
# "count_operasional", dst — padahal partials/components.html membaca "total_all",
# "total_operasional", dst. Akibatnya, setiap kali route delete_component_action
# me-render ulang components.html, ke-4 kartu statistik tampil 0 (default Jinja).
# Definisi ganda tsb sudah dihapus; fungsi di atas (baris ~93) yang dipertahankan
# karena key-nya sudah cocok dengan template.
