"""
Service Komponen dengan Auto-Diff History Engine.

Semua fungsi di sini mengendalikan logik untuk MasterComponent, Component (v2),
dan ComponentHistory. Fungsi lama tetap ada di asset_service.py untuk kompatibiliti
dengan router yang sedia ada.
"""

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.domain import Asset, Component, ComponentHistory, MasterComponent, SystemLogs, get_utc_now
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


# Peta field spesifikasi teks → label ramah pengguna untuk Audit Trail
_TEXT_FIELD_LABELS: dict[str, str] = {
    "identitas_pc": "Identitas PC",
    "jenis_pc":     "Kategori PC",
    "cpu":          "Processor (CPU)",
    "mainboard":    "Mainboard",
    "ram":          "Kapasitas RAM",
    "storage":      "Penyimpanan (Storage)",
    "vga":          "Kartu Grafis (VGA)",
    "os":           "Sistem Operasi (OS)",
}


def _detect_changes(old: Component, new_data: ComponentUpdateV2) -> list[str]:
    """
    Bandingkan nilai teks lama dan baharu untuk setiap spesifikasi.
    Kembalikan senarai perubahan manusiawi.
    """
    changes: list[str] = []

    field_mapping = {
        "identitas_pc": (old.user_pc, new_data.identitas_pc or new_data.name),
        "jenis_pc":     (old.jenis_pc, new_data.jenis_pc or new_data.pc_type),
        "cpu":          (old.cpu, new_data.cpu or new_data.processor_spec),
        "mainboard":    (old.mainboard, new_data.mainboard or new_data.mainboard_spec),
        "ram":          (old.ram, new_data.ram or new_data.ram_spec),
        "storage":      (old.storage, new_data.storage or new_data.storage_spec),
        "vga":          (old.vga, new_data.vga or new_data.vga_spec),
        "os":           (old.os, new_data.os or new_data.os_name),
    }

    for key, label in _TEXT_FIELD_LABELS.items():
        old_val, new_val = field_mapping.get(key, (None, None))
        if new_val is not None:
            clean_old = (old_val or "").strip()
            if clean_old == "-":
                clean_old = ""
            clean_new = new_val.strip()
            if clean_old != clean_new:
                from_str = clean_old if clean_old else "Kosong"
                to_str = clean_new if clean_new else "Dikosongkan"
                changes.append(f"{label}: [{from_str}] -> [{to_str}]")

    # Bandingkan field keyboard & mouse jika dibekalkan
    if new_data.keyboard is not None and (old.keyboard or "").strip() != new_data.keyboard.strip():
        changes.append(f"Keyboard: [{old.keyboard or '-'}] -> [{new_data.keyboard or '-'}]")
    if new_data.mouse is not None and (old.mouse or "").strip() != new_data.mouse.strip():
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
    try:
        db.commit()
        db.refresh(new_master)
        return new_master
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menambahkan master komponen: {str(e)}")


def delete_master(db: Session, master_id: int) -> dict:
    master = db.query(MasterComponent).filter(MasterComponent.id == master_id).first()
    if not master:
        raise HTTPException(status_code=404, detail="Master komponen tidak ditemukan.")
    db.delete(master)
    try:
        db.commit()
        return {"message": f"Master komponen '{master.name}' berhasil dihapus."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menghapus master komponen: {str(e)}")


# ==========================================
# COMPONENT v2 CRUD (Input Manual Bebas String)
# ==========================================

def get_component_by_asset(db: Session, asset_id: int) -> Component | None:
    """Ambil spesifikasi PC berdasarkan asset_id yang masih aktif."""
    return (
        db.query(Component)
        .options(
            joinedload(Component.asset),
            joinedload(Component.cpu_ref),
            joinedload(Component.ram_ref),
            joinedload(Component.storage_ref),
            joinedload(Component.os_ref),
            joinedload(Component.mainboard_ref),
            joinedload(Component.vga_ref),
            joinedload(Component.monitor_ref),
        )
        .filter(
            Component.asset_id == asset_id,
            Component.is_deleted == False
        )
        .first()
    )


def get_component_history(db: Session, component_id: int) -> list[ComponentHistory]:
    """Ambil seluruh riwayat perubahan untuk satu komponen."""
    return (
        db.query(ComponentHistory)
        .filter(ComponentHistory.component_id == component_id)
        .order_by(ComponentHistory.created_at.desc())
        .all()
    )


def create_component_v2(db: Session, data: ComponentCreateV2, user_id: int) -> Component:
    """
    Daftarkan spesifikasi PC baru dengan teks mentah tanpa kekangan Aset Induk atau Master FK.
    Menerapkan transaksi atomik (db.commit / db.rollback).
    """
    pc_name = (data.identitas_pc or data.name or "").strip()
    if not pc_name:
        raise HTTPException(status_code=400, detail="Identitas PC (User / Nama PC) wajib diisi.")

    pc_type = data.jenis_pc or data.pc_type or "PC Operasional"

    try:
        db_comp = Component(
            name=pc_name,
            pc_type=pc_type,
            processor_spec=data.cpu or data.processor_spec,
            mainboard_spec=data.mainboard or data.mainboard_spec,
            ram_spec=data.ram or data.ram_spec,
            storage_spec=data.storage or data.storage_spec,
            vga_spec=data.vga or data.vga_spec,
            os_name=data.os or data.os_name,
            monitor=data.monitor,
            keyboard=data.keyboard,
            mouse=data.mouse,
            asset_id=data.asset_id,
            is_deleted=False,
        )
        db.add(db_comp)
        db.flush()

        # Rekodkan ciptaan awal di audit trail
        history = ComponentHistory(
            component_id=db_comp.id,
            user_id=user_id,
            action_type="CREATE",
            changes_detail=f"Pendaftaran awal spesifikasi PC '{pc_name}' ({pc_type}).",
        )
        db.add(history)
        db.commit()
        db.refresh(db_comp)
        return db_comp
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal mendaftarkan spesifikasi PC: {str(e)}")


def update_component_v2(
    db: Session, component_id: int, data: ComponentUpdateV2, user_id: int
) -> Component:
    """
    Kemaskini spesifikasi PC dengan teks mentah dan enjin Auto-Diff audit trail.
    Menerapkan transaksi atomik (db.commit / db.rollback).
    """
    db_comp = db.query(Component).filter(
        Component.id == component_id,
        Component.is_deleted == False
    ).first()
    if not db_comp:
        raise HTTPException(status_code=404, detail="Spesifikasi PC tidak dijumpai atau telah dinonaktifkan.")

    # ── AUTO-DIFF ENGINE ─────────────────────────────────────────────────────
    changes = _detect_changes(db_comp, data)

    # Terapkan perubahan ke ORM object
    pc_name = (data.identitas_pc or data.name or "").strip()
    if pc_name:
        db_comp.name = pc_name

    pc_type = data.jenis_pc or data.pc_type
    if pc_type:
        db_comp.pc_type = pc_type

    if data.cpu is not None or data.processor_spec is not None:
        db_comp.processor_spec = data.cpu or data.processor_spec
    if data.mainboard is not None or data.mainboard_spec is not None:
        db_comp.mainboard_spec = data.mainboard or data.mainboard_spec
    if data.ram is not None or data.ram_spec is not None:
        db_comp.ram_spec = data.ram or data.ram_spec
    if data.storage is not None or data.storage_spec is not None:
        db_comp.storage_spec = data.storage or data.storage_spec
    if data.vga is not None or data.vga_spec is not None:
        db_comp.vga_spec = data.vga or data.vga_spec
    if data.os is not None or data.os_name is not None:
        db_comp.os_name = data.os or data.os_name

    if data.keyboard is not None:
        db_comp.keyboard = data.keyboard
    if data.mouse is not None:
        db_comp.mouse = data.mouse
    if data.monitor is not None:
        db_comp.monitor = data.monitor

    # Simpan ke ComponentHistory jika ada perubahan atau alasan diberikan
    reason = (data.update_reason or "").strip()
    if not reason and changes:
        reason = "Kemas kini spesifikasi PC"

    try:
        if reason or changes:
            action_type = _classify_action(reason, changes)
            detail_log = f"Alasan: {reason}" if reason else "Kemas kini spesifikasi"
            if changes:
                detail_log += " | " + " | ".join(changes)

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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal memperbarui spesifikasi PC: {str(e)}")


def soft_delete_component(
    db: Session,
    component_id: int,
    user_id: int | None = None,
    client_ip: str | None = None,
) -> dict:
    """
    Soft Delete untuk spesifikasi PC.
    1. Mengubah is_deleted = True, mengisi deleted_at dan deleted_by.
    2. Menambahkan entri DECOMMISSION ke ComponentHistory (riwayat upgrade/spec tetap utuh).
    3. Menambahkan log forensik digital ke SystemLogs.
    4. Seluruh proses dieksekusi secara ATOMIK dalam 1 transaksi database.
    """
    comp = db.query(Component).filter(
        Component.id == component_id,
        Component.is_deleted == False
    ).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Data Komponen tidak ditemukan atau sudah dihapus.")

    pc_name = comp.name or comp.user_pc or f"ID-{comp.id}"
    pc_type = comp.pc_type or "PC"

    try:
        # 1. Soft Delete pada entitas utama
        comp.is_deleted = True
        comp.deleted_at = get_utc_now()
        comp.deleted_by = user_id

        # 2. Catat DECOMMISSION ke riwayat komponen (relasi tetap utuh)
        history_entry = ComponentHistory(
            component_id=comp.id,
            user_id=user_id,
            action_type="DECOMMISSION",
            changes_detail=f"Spesifikasi PC '{pc_name}' dinonaktifkan (Soft Delete) oleh Super Admin. Status: Decommissioned.",
        )
        db.add(history_entry)

        # 3. Catat audit forensik ke SystemLogs
        log_entry = SystemLogs(
            user_id=user_id,
            action=f"SOFT_DELETE: Menonaktifkan spesifikasi PC '{pc_name}' ({pc_type})",
            entity="Component",
            entity_id=component_id,
            ip_address=client_ip,
            timestamp=get_utc_now(),
        )
        db.add(log_entry)

        # 4. Kunci transaksi atomik
        db.commit()
        return {"message": f"Spesifikasi PC '{pc_name}' berhasil dinonaktifkan (Soft Delete) dan tercatat di Audit Trail."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menghapus komponen. Transaksi dibatalkan: {str(e)}")


# ==========================================
# AGREGASI STATISTIK KARTU KOMPONEN (RINGAN & RAMAH MEMORI)
# ==========================================

def get_component_stats(db: Session) -> dict:
    """
    Fungsi agregat khusus untuk menghitung indikator kartu statistik PC.
    Hanya mengeksekusi COUNT() di MySQL tanpa memuat seluruh baris objek ke memori.
    """
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
            # Mengakomodasi "PC Operasional", "Operasional", atau tipe default lainnya
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

