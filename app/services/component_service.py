"""
Service Komponen dengan Auto-Diff History Engine.

Semua fungsi di sini mengendalikan logik untuk MasterComponent, Component (v2),
dan ComponentHistory. Fungsi lama tetap ada di asset_service.py untuk kompatibiliti
dengan router yang sedia ada.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.domain import Asset, Component, ComponentHistory, MasterComponent
from app.models.schemas.component import (
    ComponentCreateV2,
    ComponentUpdateV2,
    MasterComponentCreate,
)


# ==========================================
# FUNGSI BANTUAN DALAMAN
# ==========================================

def _get_master_name(db: Session, master_id: int | None) -> str:
    """Resolve ID ke nama komponen dari master_components. Fallback ke 'Tidak Ditetapkan'."""
    if not master_id:
        return "Tidak Ditetapkan"
    master = db.query(MasterComponent).filter(MasterComponent.id == master_id).first()
    return master.name if master else "Tidak Ditetapkan"


# Peta field FK → label yang lebih ramah pengguna untuk log audit
_FIELD_LABELS: dict[str, str] = {
    "os_id":        "OS",
    "cpu_id":       "CPU",
    "mainboard_id": "Mainboard",
    "ram_id":       "RAM",
    "vga_id":       "VGA/GPU",
    "storage_id":   "Storage",
    "monitor_id":   "Monitor",
}


def _detect_changes(db: Session, old: Component, new_data: ComponentUpdateV2) -> list[str]:
    """
    Bandingkan nilai lama dan baharu untuk setiap field FK.
    Kembalikan senarai perubahan dalam format manusiawi.

    Cth: ["RAM: [8GB DDR4 3200MHz] -> [16GB DDR4 3200MHz]"]
    """
    changes: list[str] = []

    for field, label in _FIELD_LABELS.items():
        old_id = getattr(old, field)
        new_id = getattr(new_data, field, None)

        if old_id != new_id:
            old_name = _get_master_name(db, old_id)
            new_name = _get_master_name(db, new_id)
            changes.append(f"{label}: [{old_name}] -> [{new_name}]")

    # Bandingkan field free-text (keyboard & mouse)
    if old.keyboard != new_data.keyboard:
        changes.append(f"Keyboard: [{old.keyboard or '-'}] -> [{new_data.keyboard or '-'}]")
    if old.mouse != new_data.mouse:
        changes.append(f"Mouse: [{old.mouse or '-'}] -> [{new_data.mouse or '-'}]")

    return changes


def _classify_action(reason: str, changes: list[str]) -> str:
    """
    Tentukan jenis tindakan berdasarkan alasan yang diberikan pengguna.
    Semak kata kunci tanpa-sensitif huruf besar/kecil.
    """
    lower = reason.lower()
    if any(kw in lower for kw in ["upgrade", "naik taraf", "tingkat"]):
        return "UPGRADE"
    if any(kw in lower for kw in ["downgrade", "turun taraf"]):
        return "DOWNGRADE"
    if any(kw in lower for kw in ["ganti", "replace", "tukar", "rosak", "rusak"]):
        return "REPLACE"
    if any(kw in lower for kw in ["baiki", "repair", "servis"]):
        return "REPAIR"
    return "UPDATE"


# ==========================================
# MASTER COMPONENT CRUD
# ==========================================

def get_all_masters(db: Session, category: str | None = None) -> list[MasterComponent]:
    query = db.query(MasterComponent)
    if category:
        query = query.filter(MasterComponent.category == category)
    return query.order_by(MasterComponent.category, MasterComponent.name).all()


def create_master(db: Session, data: MasterComponentCreate) -> MasterComponent:
    # Tolak nama duplikat agar dropdown tetap bersih
    existing = db.query(MasterComponent).filter(MasterComponent.name == data.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Komponen '{data.name}' sudah ada dalam master data.")

    new_master = MasterComponent(**data.model_dump())
    db.add(new_master)
    db.commit()
    db.refresh(new_master)
    return new_master


def delete_master(db: Session, master_id: int) -> dict:
    master = db.query(MasterComponent).filter(MasterComponent.id == master_id).first()
    if not master:
        raise HTTPException(status_code=404, detail="Master komponen tidak ditemukan.")
    db.delete(master)
    db.commit()
    return {"message": f"Master komponen '{master.name}' berhasil dihapus."}


# ==========================================
# COMPONENT v2 CRUD (dengan Auto-Diff)
# ==========================================

def get_component_by_asset(db: Session, asset_id: int) -> Component | None:
    """Ambil spesifikasi PC berdasarkan asset_id."""
    return db.query(Component).filter(Component.asset_id == asset_id).first()


def get_component_history(db: Session, component_id: int) -> list[ComponentHistory]:
    """Ambil seluruh riwayat perubahan untuk satu komponen."""
    return (
        db.query(ComponentHistory)
        .filter(ComponentHistory.component_id == component_id)
        .order_by(ComponentHistory.created_at.desc())
        .all()
    )


def _get_master_text(db: Session, master_id: int | None) -> str | None:
    if not master_id:
        return None
    master = db.query(MasterComponent).filter(MasterComponent.id == master_id).first()
    return master.name if master else None


def create_component_v2(db: Session, data: ComponentCreateV2, user_id: int) -> Component:
    # Pastikan aset induk wujud
    asset = db.query(Asset).filter(Asset.id == data.asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Aset induk tidak dijumpai.")

    # Tolak pendaftaran ganda pada aset yang sama
    existing = db.query(Component).filter(Component.asset_id == data.asset_id).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Aset ID {data.asset_id} sudah memiliki spesifikasi PC. Gunakan fungsi Edit untuk mengubahnya.",
        )

    pc_name = (asset.nama or f"PC {asset.kode_aset or data.asset_id}")[:100]

    db_comp = Component(
        asset_id=data.asset_id,
        name=pc_name,
        pc_type=data.jenis_pc,
        os_id=data.os_id,
        cpu_id=data.cpu_id,
        mainboard_id=data.mainboard_id,
        ram_id=data.ram_id,
        vga_id=data.vga_id,
        storage_id=data.storage_id,
        monitor_id=data.monitor_id,
        os_name=_get_master_text(db, data.os_id),
        processor_spec=_get_master_text(db, data.cpu_id),
        mainboard_spec=_get_master_text(db, data.mainboard_id),
        ram_spec=_get_master_text(db, data.ram_id),
        vga_spec=_get_master_text(db, data.vga_id),
        storage_spec=_get_master_text(db, data.storage_id),
        monitor=_get_master_text(db, data.monitor_id),
        keyboard=data.keyboard,
        mouse=data.mouse,
    )
    db.add(db_comp)
    db.flush()  # Dapatkan ID sebelum commit penuh

    # Rekodkan ciptaan awal di audit trail
    history = ComponentHistory(
        component_id=db_comp.id,
        user_id=user_id,
        action_type="CREATE",
        changes_detail=f"Pendaftaran awal spesifikasi PC untuk aset '{pc_name}'.",
    )
    db.add(history)
    db.commit()
    db.refresh(db_comp)
    return db_comp


def update_component_v2(
    db: Session, component_id: int, data: ComponentUpdateV2, user_id: int
) -> Component:
    db_comp = db.query(Component).filter(Component.id == component_id).first()
    if not db_comp:
        raise HTTPException(status_code=404, detail="Spesifikasi PC tidak dijumpai.")

    # ── AUTO-DIFF ENGINE ─────────────────────────────────────────────────────
    changes = _detect_changes(db, db_comp, data)

    # Terapkan perubahan ke ORM object
    for field in _FIELD_LABELS:
        setattr(db_comp, field, getattr(data, field, None))

    # Sinkronisasi ke kolom free-text
    db_comp.os_name = _get_master_text(db, data.os_id) or db_comp.os_name
    db_comp.processor_spec = _get_master_text(db, data.cpu_id) or db_comp.processor_spec
    db_comp.mainboard_spec = _get_master_text(db, data.mainboard_id) or db_comp.mainboard_spec
    db_comp.ram_spec = _get_master_text(db, data.ram_id) or db_comp.ram_spec
    db_comp.vga_spec = _get_master_text(db, data.vga_id) or db_comp.vga_spec
    db_comp.storage_spec = _get_master_text(db, data.storage_id) or db_comp.storage_spec
    if data.monitor_id:
        db_comp.monitor = _get_master_text(db, data.monitor_id)

    db_comp.pc_type   = data.jenis_pc
    db_comp.keyboard  = data.keyboard
    db_comp.mouse     = data.mouse

    # Simpan ke ComponentHistory hanya jika ada perubahan sebenar
    if changes:
        action_type = _classify_action(data.update_reason, changes)
        detail_log = f"Alasan: {data.update_reason} | " + " | ".join(changes)

        history = ComponentHistory(
            component_id=db_comp.id,
            user_id=user_id,
            action_type=action_type,
            changes_detail=detail_log,
        )
        db.add(history)

    db.commit()
    db.refresh(db_comp)
    return db_comp
