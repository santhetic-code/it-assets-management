import io
from datetime import date
from typing import List, Optional

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.domain import Asset, Component, MaintenanceLog, NetworkIP, Purchase
from app.models.schemas.asset import AssetCreate, AssetUpdate
from app.models.schemas.component import ComponentCreate, ComponentUpdate
from app.models.schemas.maintenance import MaintenanceCreate, MaintenanceUpdate
from app.models.schemas.purchase import PurchaseCreate, PurchaseUpdate


# ==========================================
# 1. LOGIKA ASET
# ==========================================
def get_all_assets(db: Session):
    return db.query(Asset).all()


def get_asset_by_tag(db: Session, tag: str):
    return db.query(Asset).filter(Asset.asset_tag == tag).first()


def create_asset(db: Session, asset_data: AssetCreate):
    new_asset = Asset(**asset_data.model_dump())
    try:
        db.add(new_asset)
        db.commit()
        db.refresh(new_asset)
        return new_asset
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag Aset '{asset_data.asset_tag}' sudah terdaftar.",
        )


def update_asset(db: Session, asset_id: int, asset_data: AssetUpdate):
    db_asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not db_asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan.")

    update_data = asset_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_asset, key, value)

    try:
        db.commit()
        db.refresh(db_asset)
        return db_asset
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Tag Aset bertabrakan dengan data lain."
        )


def delete_asset(db: Session, asset_id: int):
    db_asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not db_asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan.")
    db.delete(db_asset)
    db.commit()
    return {"message": "Aset berhasil dihapus."}


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
def get_components(db: Session):
    return db.query(Component).all()


def create_component(db: Session, data: ComponentCreate):
    new_item = Component(**data.model_dump(exclude_unset=True))
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item


def update_component(db: Session, item_id: int, data: ComponentUpdate):
    db_item = db.query(Component).filter(Component.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Data Komponen tidak ditemukan.")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_component(db: Session, item_id: int):
    item = db.query(Component).filter(Component.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Data Komponen tidak ditemukan.")
    db.delete(item)
    db.commit()
    return {"message": "Komponen berhasil dihapus."}


async def import_components_from_file(db: Session, file: UploadFile):
    import uuid

    if not file.filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=400, detail="Format file tidak didukung. Gunakan .csv atau .xlsx"
        )

    try:
        contents = await file.read()
        if file.filename.endswith(".csv"):
            # Jika CSV, jadikan satu dictionary agar seragam dengan Excel
            df_dict = {"Sheet1": pd.read_csv(io.BytesIO(contents))}
        else:
            # sheet_name=None akan membaca SELURUH sheet yang ada di file Excel
            df_dict = pd.read_excel(io.BytesIO(contents), sheet_name=None)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file: {str(e)}")

    imported_count = 0
    errors = []

    # Looping untuk setiap sheet di dalam file Excel
    for sheet_name, df in df_dict.items():
        # Standarisasi nama kolom (huruf besar & hilangkan spasi)
        df.columns = df.columns.astype(str).str.strip().str.upper()

        # Deteksi otomatis: Lewati sheet yang tidak memiliki kolom 'USER' (misal: sheet IP List atau Report AC)
        if "USER" not in df.columns:
            continue

        for index, row in df.iterrows():
            pc_name = str(row.get("USER", "")).strip()

            if (
                not pc_name
                or pd.isna(pc_name)
                or pc_name.lower() == "nan"
                or pc_name.lower() == "user"
            ):
                continue

            # Cek apakah Aset Induk sudah ada di database
            asset = (
                db.query(Asset)
                .filter(
                    (Asset.name.ilike(f"%{pc_name}%"))
                    | (Asset.assigned_to.ilike(f"%{pc_name}%"))
                )
                .first()
            )

            # FITUR BARU: Auto-Create Aset Induk jika belum ada
            if not asset:
                auto_tag = f"PC-{uuid.uuid4().hex[:6].upper()}"
                new_asset = Asset(
                    asset_tag=auto_tag,
                    name=pc_name,
                    category="Hardware/PC",
                    status="Digunakan",
                    condition="Baru",
                    assigned_to=pc_name,
                )
                db.add(new_asset)
                db.flush()  # Dapatkan ID aset yang baru dibuat sebelum di-commit
                asset = new_asset

            # Ekstraksi Data Spesifikasi PC
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
                psu=str(row.get("PSU", "")),
                casing=str(row.get("CASSING", row.get("CASING", ""))),
            )

            # Bersihkan nilai 'nan' dari pandas
            for key, value in list(new_component.__dict__.items()):
                if isinstance(value, str) and value.lower() == "nan":
                    setattr(new_component, key, None)

            db.add(new_component)
            imported_count += 1

    # Simpan semua data (Aset baru & Komponen) ke database
    db.commit()

    return {
        "status": "success",
        "message": f"Berhasil mengimpor {imported_count} data komponen PC.",
        "errors": errors,
        "count": imported_count,
    }


# ==========================================
# 3. LOGIKA PEMBELIAN
# ==========================================
def get_purchases(db: Session):
    return db.query(Purchase).all()


def create_purchase(db: Session, data: PurchaseCreate):
    purchase_data = data.model_dump(exclude_unset=True)
    qty = purchase_data.get("quantity", 1) or 1
    unit_price = purchase_data.get("price_per_item", purchase_data.get("cost", 0.0)) or 0.0
    purchase_data["cost"] = unit_price
    purchase_data["price_per_item"] = unit_price
    purchase_data["quantity"] = qty
    purchase_data["total_price"] = unit_price * qty

    new_item = Purchase(**purchase_data)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item


def update_purchase(db: Session, item_id: int, data: PurchaseUpdate):
    db_item = db.query(Purchase).filter(Purchase.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Data Pembelian tidak ditemukan.")

    update_data = data.model_dump(exclude_unset=True)
    if "price_per_item" in update_data or "quantity" in update_data or "cost" in update_data:
        unit_price = update_data.get(
            "price_per_item", update_data.get("cost", db_item.price_per_item or db_item.cost or 0.0)
        )
        qty = update_data.get("quantity", db_item.quantity or 1)
        update_data["cost"] = unit_price
        update_data["price_per_item"] = unit_price
        update_data["quantity"] = qty
        update_data["total_price"] = float(unit_price) * int(qty)

    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_purchase(db: Session, item_id: int):
    item = db.query(Purchase).filter(Purchase.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Data Pembelian tidak ditemukan.")
    db.delete(item)
    db.commit()
    return {"message": "Riwayat pembelian berhasil dihapus."}


# ==========================================
# 4. LOGIKA MAINTENANCE
# ==========================================
def get_all_maintenance(db: Session):
    logs = db.query(MaintenanceLog).all()
    today = date.today()
    is_changed = False

    # Auto-flagging: Mengubah status otomatis jika tanggal lewat
    for log in logs:
        if (
            log.next_schedule_date
            and log.next_schedule_date <= today
            and log.status == "Aman"
        ):
            log.status = "Kritis"
            is_changed = True

    if is_changed:
        db.commit()

    return logs


def create_maintenance(db: Session, data: MaintenanceCreate):
    new_item = MaintenanceLog(**data.model_dump(exclude_unset=True))
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item


def update_maintenance(db: Session, item_id: int, data: MaintenanceUpdate):
    db_item = db.query(MaintenanceLog).filter(MaintenanceLog.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Data Maintenance tidak ditemukan.")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_maintenance(db: Session, item_id: int):
    item = db.query(MaintenanceLog).filter(MaintenanceLog.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Data Maintenance tidak ditemukan.")
    db.delete(item)
    db.commit()
    return {"message": "Jadwal maintenance berhasil dihapus."}


# ==========================================
# 5. STATISTIK DASHBOARD DINAMIS
# ==========================================
def get_dashboard_stats(db: Session):
    total_assets = db.query(Asset).count()
    total_components = db.query(Component).count()
    active_ips = db.query(NetworkIP).filter(NetworkIP.status == "Aktif").count()

    all_maintenance = get_all_maintenance(db)
    pending_maintenance = sum(1 for m in all_maintenance if m.status == "Kritis")

    status_query = (
        db.query(Asset.status, func.count(Asset.id)).group_by(Asset.status).all()
    )
    if status_query:
        status_labels = [row[0] for row in status_query]
        status_data = [row[1] for row in status_query]
    else:
        status_labels = ["Digunakan", "Tersedia", "Rusak"]
        status_data = [0, 0, 0]

    category_query = (
        db.query(Asset.category, func.count(Asset.id)).group_by(Asset.category).all()
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
