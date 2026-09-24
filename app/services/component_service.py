from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import exc
from typing import List, Optional
from app.models.domain import Component, ComponentHistory
from app.models.schemas.component import ComponentCreate, ComponentUpdate


def get_utc_now():
    return datetime.now(timezone.utc)


def get_components(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Component).filter(Component.is_deleted == False).offset(skip).limit(limit).all()


def get_component(db: Session, component_id: int):
    return db.query(Component).filter(Component.id == component_id, Component.is_deleted == False).first()


def create_component(db: Session, component: ComponentCreate, current_user_id: int):
    # Buat komponen baru dengan strict foreign keys
    db_component = Component(
        name=component.name,
        pc_type=component.pc_type,
        asset_id=component.asset_id,
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

    # Catat ke History (Audit Trail)
    history_entry = ComponentHistory(
        component_id=db_component.id,
        user_id=current_user_id,
        action_type="CREATE",
        changes_detail=f"Pendaftaran spesifikasi PC: '{db_component.name}' ({db_component.pc_type})",
        created_at=get_utc_now()
    )
    db.add(history_entry)
    db.commit()

    return db_component


def update_component(db: Session, component_id: int, component_data: ComponentUpdate, current_user_id: int):
    db_comp = get_component(db, component_id)
    if not db_comp:
        return None

    # Simpan state lama untuk perbandingan (Audit Trail)
    old_state = {
        "name": db_comp.name,
        "pc_type": db_comp.pc_type,
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

    # Update data
    update_data = component_data.model_dump(exclude_unset=True)
    
    # Ambil alasan dari update_data lalu hapus agar tidak masuk ke model Component
    update_reason = update_data.pop("update_reason", None)

    for key, value in update_data.items():
        setattr(db_comp, key, value)
    
    db_comp.updated_at = get_utc_now()
    db.commit()
    db.refresh(db_comp)

    # Deteksi perubahan untuk Audit Trail
    changes = []
    for key, old_val in old_state.items():
        new_val = getattr(db_comp, key)
        if str(old_val) != str(new_val):
            changes.append(f"{key}: [{old_val}] -> [{new_val}]")

    if changes:
        reason_text = f"Alasan: {update_reason} | " if update_reason else ""
        action_type = "UPDATE"
        # Logika sederhana penentuan aksi: jika memori/storage berubah -> UPGRADE/DOWNGRADE (bisa dikembangkan)
        if "ram_id" in str(changes) or "storage_id" in str(changes):
            action_type = "UPGRADE/DOWNGRADE"

        history_entry = ComponentHistory(
            component_id=db_comp.id,
            user_id=current_user_id,
            action_type=action_type,
            changes_detail=reason_text + " | ".join(changes),
            created_at=get_utc_now()
        )
        db.add(history_entry)
        db.commit()

    return db_comp


def delete_component(db: Session, component_id: int, current_user_id: int):
    # Menggunakan Soft Delete
    db_comp = get_component(db, component_id)
    if db_comp:
        db_comp.is_deleted = True
        db_comp.deleted_at = get_utc_now()
        db_comp.deleted_by = current_user_id
        
        # Catat di history
        history = ComponentHistory(
            component_id=db_comp.id,
            user_id=current_user_id,
            action_type="DECOMMISSION",
            changes_detail=f"Spesifikasi PC dinonaktifkan (Soft Delete)",
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


def get_component_stats(db: Session) -> dict:
    from sqlalchemy import func
    counts = (
        db.query(Component.pc_type, func.count(Component.id))
        .filter(Component.is_deleted == False)
        .group_by(Component.pc_type)
        .all()
    )

    total_op = 0
    total_srv = 0
    total_bkp = 0
    total_all = 0

    for pc_type, cnt in counts:
        total_all += cnt
        pt = (pc_type or "").strip().lower()
        if "server" in pt:
            total_srv += cnt
        elif "backup" in pt:
            total_bkp += cnt
        else:
            total_op += cnt

    pct_op = round((total_op / total_all) * 100) if total_all > 0 else 0
    pct_srv = round((total_srv / total_all) * 100) if total_all > 0 else 0
    pct_bkp = round((total_bkp / total_all) * 100) if total_all > 0 else 0

    return {
        "count_total": total_all,
        "count_operasional": total_op,
        "count_server": total_srv,
        "count_backup": total_bkp,
        "pct_operasional": pct_op,
        "pct_server": pct_srv,
        "pct_backup": pct_bkp,
    }
