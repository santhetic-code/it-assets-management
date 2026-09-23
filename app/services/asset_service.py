import io
from datetime import date
from typing import List, Optional

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.domain import Asset, Component, MaintenanceLog, NetworkIP, Purchase, SystemLogs, get_utc_now
from app.models.schemas.asset import AssetCreate, AssetUpdate
from app.models.schemas.component import ComponentCreate, ComponentUpdate
from app.models.schemas.maintenance import MaintenanceCreate, MaintenanceUpdate
from app.models.schemas.purchase import PurchaseCreate, PurchaseUpdate


# ==========================================
# 1. LOGIKA ASET
# ==========================================
def get_assets(db: Session, skip: int = 0, limit: int = 1000):
    # Mengambil semua data aset aktif (dibatasi 1000 agar tidak berat)
    return db.query(Asset).filter(Asset.is_deleted == False).offset(skip).limit(limit).all()


def get_all_assets(db: Session):
    return get_assets(db)


def get_asset_by_tag(db: Session, tag: str):
    return db.query(Asset).filter(Asset.asset_tag == tag, Asset.is_deleted == False).first()


def create_asset(db: Session, asset: AssetCreate):
    # Memasukkan data baru ke database dengan transaksi atomik
    db_asset = Asset(**asset.model_dump(), is_deleted=False)
    db.add(db_asset)
    try:
        db.commit()
        db.refresh(db_asset)
        return db_asset
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menambahkan aset: {str(e)}")


def update_asset(db: Session, asset_id: int, asset: AssetUpdate):
    # Mencari aset aktif berdasarkan ID lalu menimpanya dengan data baru
    db_asset = db.query(Asset).filter(Asset.id == asset_id, Asset.is_deleted == False).first()
    if not db_asset:
        return None
    for key, value in asset.model_dump().items():
        setattr(db_asset, key, value)
    try:
        db.commit()
        db.refresh(db_asset)
        return db_asset
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal memperbarui aset: {str(e)}")


def delete_asset(db: Session, asset_id: int, user_id: int | None = None, client_ip: str | None = None):
    # Soft Delete aset agar data historis dan relasi tidak musnah
    db_asset = db.query(Asset).filter(Asset.id == asset_id, Asset.is_deleted == False).first()
    if not db_asset:
        return False

    asset_name = db_asset.nama or db_asset.name or f"ID-{db_asset.id}"
    try:
        db_asset.is_deleted = True
        db_asset.deleted_at = get_utc_now()
        db_asset.deleted_by = user_id

        # Catat forensik ke SystemLogs
        log_entry = SystemLogs(
            user_id=user_id,
            action=f"SOFT_DELETE: Menonaktifkan aset '{asset_name}' (Tag: {db_asset.kode_aset or '-'})",
            entity="Asset",
            entity_id=asset_id,
            ip_address=client_ip,
            timestamp=get_utc_now(),
        )
        db.add(log_entry)

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menonaktifkan aset: {str(e)}")


def import_assets_from_file(db: Session, file_bytes: bytes, filename: str) -> int:
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Gagal membaca file impor: {str(e)}"
        )

    col_map = {
        "Tag Aset": "asset_tag",
        "tag": "asset_tag",
        "asset_tag": "asset_tag",
        "Nama Perangkat": "name",
        "nama": "name",
        "name": "name",
        "Nama Aset": "name",
        "Kategori": "category",
        "category": "category",
        "SN": "serial_number",
        "sn": "serial_number",
        "serial_number": "serial_number",
        "SN / PID": "serial_number",
        "Pengguna": "assigned_to",
        "assigned_to": "assigned_to",
        "Di Gunakan Oleh": "assigned_to",
        "Lokasi": "location",
        "location": "location",
        "Kondisi": "condition",
        "condition": "condition",
        "Status": "status",
        "status": "status",
        "usage_status": "status",
    }
    df.rename(
        columns=lambda c: col_map.get(str(c).strip(), str(c).strip()), inplace=True
    )

    imported_count = 0
    for _, row in df.iterrows():
        tag = str(row.get("asset_tag", "")).strip()
        if not tag or tag.lower() == "nan":
            continue

        existing = db.query(Asset).filter(Asset.asset_tag == tag).first()
        asset_values = {
            "asset_tag": tag,
            "name": str(row.get("name", "Unnamed Asset")),
            "category": str(row.get("category", "Fasilitas")),
            "serial_number": str(row.get("serial_number", "-")),
            "assigned_to": str(row.get("assigned_to", "-")),
            "location": str(row.get("location", "-")),
            "condition": str(row.get("condition", "Baru")),
            "status": str(row.get("status", "Digunakan")),
        }
        if existing:
            for k, v in asset_values.items():
                setattr(existing, k, v)
        else:
            new_a = Asset(**asset_values)
            db.add(new_a)
        imported_count += 1

    try:
        db.commit()
        return imported_count
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"Gagal menyimpan data impor: {str(e)}"
        )


# ==========================================
# 2. LOGIKA KOMPONEN
# ==========================================
def get_components(db: Session, pc_type: Optional[str] = None):
    query = (
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
        .filter(Component.is_deleted == False)
    )
    if pc_type and pc_type != "semua":
        query = query.filter(
            or_(
                Component.pc_type == pc_type,
                Component.pc_type == f"PC {pc_type}",
                Component.pc_type == pc_type.replace("PC ", ""),
            )
        )
    return query.all()


def create_component(db: Session, data: ComponentCreate):
    new_item = Component(**data.model_dump(exclude_unset=True), is_deleted=False)
    db.add(new_item)
    try:
        db.commit()
        db.refresh(new_item)
        return new_item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menambahkan komponen: {str(e)}")


def update_component(db: Session, item_id: int, data: ComponentUpdate):
    db_item = db.query(Component).filter(Component.id == item_id, Component.is_deleted == False).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Data Komponen tidak ditemukan.")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    try:
        db.commit()
        db.refresh(db_item)
        return db_item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal memperbarui komponen: {str(e)}")


def delete_component(db: Session, item_id: int, user_id: int | None = None, client_ip: str | None = None):
    from app.services import component_service
    return component_service.soft_delete_component(db, item_id, user_id=user_id, client_ip=client_ip)


async def import_components_from_file(db: Session, file: UploadFile):
    import uuid

    if not file.filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=400, detail="Format file tidak didukung. Gunakan .csv atau .xlsx"
        )

    try:
        contents = await file.read()
        if file.filename.endswith(".csv"):
            df_dict = {"Sheet1": pd.read_csv(io.BytesIO(contents))}
        else:
            df_dict = pd.read_excel(io.BytesIO(contents), sheet_name=None)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file: {str(e)}")

    imported_count = 0
    errors = []

    for sheet_name, df in df_dict.items():
        df.columns = df.columns.astype(str).str.strip().str.upper()

        required_columns = {"USER", "OS", "RAM"}
        if not required_columns.issubset(set(df.columns)):
            continue

        for index, row in df.iterrows():
            pc_name = str(row.get("USER", "")).strip()

            if (
                not pc_name
                or pd.isna(pc_name)
                or pc_name.lower() in ["nan", "user", "none", "pengguna", "-", ""]
            ):
                continue

            asset = (
                db.query(Asset)
                .filter(
                    Asset.is_deleted == False,
                    (
                        (Asset.name.ilike(f"%{pc_name}%"))
                        | (Asset.assigned_to.ilike(f"%{pc_name}%"))
                    )
                )
                .first()
            )

            if not asset:
                auto_tag = f"PC-{uuid.uuid4().hex[:6].upper()}"
                new_asset = Asset(
                    asset_tag=auto_tag,
                    name=pc_name,
                    category="Hardware/PC",
                    status="Digunakan",
                    condition="Baru",
                    assigned_to=pc_name,
                    is_deleted=False,
                )
                db.add(new_asset)
                db.flush()
                asset = new_asset

            new_component = Component(
                asset_id=asset.id,
                name=f"Spesifikasi {pc_name}",
                os_name=str(row.get("OS", "")),
                ram_spec=str(row.get("RAM", "")),
                vga_spec=str(row.get("VGA", row.get("GPU CARD", ""))),
                processor_spec=str(row.get("CPU", row.get("PROCESSOR", ""))),
                mainboard_spec=str(row.get("MAINBOARD", "")),
                storage_spec=str(row.get("HDD/SSD", "")),
                monitor=str(row.get("MONITOR", "")),
                keyboard=str(row.get("KEYBOARD", "")),
                mouse=str(row.get("MOUSE", "")),
                pc_type=str(row.get("JENIS_PC", row.get("JENIS PC", "Operasional"))),
                is_deleted=False,
            )

            for key, value in list(new_component.__dict__.items()):
                if isinstance(value, str) and value.lower() == "nan":
                    setattr(new_component, key, None)

            db.add(new_component)
            imported_count += 1

    try:
        db.commit()
        return {
            "status": "success",
            "message": f"Berhasil mengimpor {imported_count} data komponen PC.",
            "errors": errors,
            "count": imported_count,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan data impor komponen: {str(e)}")


# ==========================================
# 3. LOGIKA PEMBELIAN
# ==========================================
def get_purchases(db: Session):
    return db.query(Purchase).filter(Purchase.is_deleted == False).all()


def create_purchase(db: Session, data: PurchaseCreate):
    raw_data = data.model_dump(exclude_unset=True)
    qty = raw_data.get("quantity", 1) or 1
    unit_price = raw_data.get("unit_price", raw_data.get("price_per_item", raw_data.get("cost", 0.0))) or 0.0
    total_price = raw_data.get("total_price", float(unit_price) * int(qty))

    new_item = Purchase(
        item_name=raw_data.get("item_name"),
        vendor=raw_data.get("vendor"),
        unit_price=unit_price,
        quantity=qty,
        total_price=total_price,
        purchase_date=raw_data.get("purchase_date"),
        category=raw_data.get("category"),
        description=raw_data.get("description"),
        file_path=raw_data.get("file_path"),
        is_deleted=False,
    )
    db.add(new_item)
    try:
        db.commit()
        db.refresh(new_item)
        return new_item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menambahkan data pembelian: {str(e)}")


def update_purchase(db: Session, item_id: int, data: PurchaseUpdate):
    db_item = db.query(Purchase).filter(Purchase.id == item_id, Purchase.is_deleted == False).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Data Pembelian tidak ditemukan.")

    update_data = data.model_dump(exclude_unset=True)
    if "unit_price" in update_data or "quantity" in update_data or "price_per_item" in update_data or "cost" in update_data:
        unit_price = update_data.get(
            "unit_price", update_data.get("price_per_item", update_data.get("cost", db_item.unit_price or 0.0))
        )
        qty = update_data.get("quantity", db_item.quantity or 1)
        update_data["unit_price"] = unit_price
        update_data["quantity"] = qty
        update_data["total_price"] = float(unit_price) * int(qty)

    for key, value in update_data.items():
        if hasattr(db_item, key):
            setattr(db_item, key, value)

    try:
        db.commit()
        db.refresh(db_item)
        return db_item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal memperbarui data pembelian: {str(e)}")


def delete_purchase(db: Session, item_id: int, user_id: int | None = None, client_ip: str | None = None):
    item = db.query(Purchase).filter(Purchase.id == item_id, Purchase.is_deleted == False).first()
    if not item:
        raise HTTPException(status_code=404, detail="Data Pembelian tidak ditemukan.")

    item_name = item.item_name
    try:
        item.is_deleted = True
        item.deleted_at = get_utc_now()
        item.deleted_by = user_id

        log_entry = SystemLogs(
            user_id=user_id,
            action=f"SOFT_DELETE: Menghapus data transaksi pembelian '{item_name}'",
            entity="Purchase",
            entity_id=item_id,
            ip_address=client_ip,
            timestamp=get_utc_now(),
        )
        db.add(log_entry)

        db.commit()
        return {"message": "Riwayat pembelian berhasil dinonaktifkan (Soft Delete)."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menghapus data pembelian: {str(e)}")


# ==========================================
# 4. LOGIKA MAINTENANCE
# ==========================================
def get_all_maintenance(db: Session):
    logs = db.query(MaintenanceLog).options(joinedload(MaintenanceLog.asset)).all()
    today = date.today()
    is_changed = False

    for log in logs:
        if (
            log.next_schedule_date
            and log.next_schedule_date <= today
            and log.status == "Aman"
        ):
            log.status = "Kritis"
            is_changed = True

    if is_changed:
        try:
            db.commit()
        except Exception:
            db.rollback()

    return logs


def create_maintenance(db: Session, data: MaintenanceCreate):
    new_item = MaintenanceLog(**data.model_dump(exclude_unset=True))
    db.add(new_item)
    try:
        db.commit()
        db.refresh(new_item)
        return new_item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menambahkan jadwal maintenance: {str(e)}")


def update_maintenance(db: Session, item_id: int, data: MaintenanceUpdate):
    db_item = db.query(MaintenanceLog).filter(MaintenanceLog.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Data Maintenance tidak ditemukan.")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    try:
        db.commit()
        db.refresh(db_item)
        return db_item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal memperbarui maintenance: {str(e)}")


def delete_maintenance(db: Session, item_id: int):
    item = db.query(MaintenanceLog).filter(MaintenanceLog.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Data Maintenance tidak ditemukan.")
    db.delete(item)
    try:
        db.commit()
        return {"message": "Jadwal maintenance berhasil dihapus."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menghapus maintenance: {str(e)}")


# ==========================================
# 5. STATISTIK DASHBOARD DINAMIS
# ==========================================
def get_dashboard_stats(db: Session):
    total_assets = db.query(Asset).filter(Asset.is_deleted == False).count()
    total_components = db.query(Component).filter(Component.is_deleted == False).count()
    active_ips = db.query(NetworkIP).filter(NetworkIP.status == "Aktif").count()

    all_maintenance = get_all_maintenance(db)
    pending_maintenance = sum(1 for m in all_maintenance if m.status == "Kritis")

    status_query = (
        db.query(Asset.status, func.count(Asset.id))
        .filter(Asset.is_deleted == False)
        .group_by(Asset.status)
        .all()
    )
    if status_query:
        status_labels = [row[0] for row in status_query]
        status_data = [row[1] for row in status_query]
    else:
        status_labels = ["Digunakan", "Tersedia", "Rusak"]
        status_data = [0, 0, 0]

    category_query = (
        db.query(Asset.category, func.count(Asset.id))
        .filter(Asset.is_deleted == False)
        .group_by(Asset.category)
        .all()
    )
    if category_query:
        bar_labels = [row[0] for row in category_query]
        bar_data = [row[1] for row in category_query]
    else:
        bar_labels = ["Laptop", "PC Desktop", "Server", "Printer", "Switch"]
        bar_data = [0, 0, 0, 0, 0]

    return {
        "total_assets": total_assets,
        "total_components": total_components,
        "active_ips": active_ips,
        "pending_maintenance": pending_maintenance,
        "status_labels": status_labels,
        "status_data": status_data,
        "bar_labels": bar_labels,
        "bar_data": bar_data,
    }
