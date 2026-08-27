from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from fastapi import HTTPException, status
from datetime import date

from app.models.domain import Asset, Component, Purchase, MaintenanceLog, NetworkIP
from app.models.schemas.asset import AssetCreate, AssetUpdate
from app.models.schemas.component import ComponentCreate, ComponentUpdate
from app.models.schemas.purchase import PurchaseCreate, PurchaseUpdate
from app.models.schemas.maintenance import MaintenanceCreate, MaintenanceUpdate

# ==========================================
# 1. LOGIKA ASET (Memperbaiki Bug #8)
# ==========================================
def get_all_assets(db: Session):
    return db.query(Asset).all()

def create_asset(db: Session, asset_data: AssetCreate):
    new_asset = Asset(**asset_data.model_dump())
    try:
        db.add(new_asset)
        db.commit()
        db.refresh(new_asset)
        return new_asset
    except IntegrityError:
        db.rollback()
        # Menangkap error duplikat Tag Aset dengan elegan
        raise HTTPException(status_code=400, detail=f"Tag Aset '{asset_data.asset_tag}' sudah terdaftar.")

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
        raise HTTPException(status_code=400, detail="Tag Aset bertabrakan dengan data lain.")

def delete_asset(db: Session, asset_id: int):
    db_asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not db_asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan.")
    db.delete(db_asset)
    db.commit()
    return {"message": "Aset berhasil dihapus."}

# ==========================================
# 2. LOGIKA KOMPONEN & PEMBELIAN
# ==========================================
# (Fungsi CRUD dasar untuk Komponen)
def get_components(db: Session): return db.query(Component).all()
def create_component(db: Session, data: ComponentCreate):
    new_item = Component(**data.model_dump())
    db.add(new_item); db.commit(); db.refresh(new_item)
    return new_item
def delete_component(db: Session, item_id: int):
    item = db.query(Component).filter(Component.id == item_id).first()
    if item: db.delete(item); db.commit()
    return {"message": "Komponen dihapus."}

# (Fungsi CRUD dasar untuk Pembelian)
def get_purchases(db: Session): return db.query(Purchase).all()
def create_purchase(db: Session, data: PurchaseCreate):
    new_item = Purchase(**data.model_dump())
    db.add(new_item); db.commit(); db.refresh(new_item)
    return new_item
def delete_purchase(db: Session, item_id: int):
    item = db.query(Purchase).filter(Purchase.id == item_id).first()
    if item: db.delete(item); db.commit()
    return {"message": "Riwayat pembelian dihapus."}

# ==========================================
# 3. LOGIKA MAINTENANCE (Memperbaiki Bug #7)
# ==========================================
def get_all_maintenance(db: Session):
    logs = db.query(MaintenanceLog).all()
    today = date.today()
    is_changed = False
    
    # Auto-flagging: Mengubah status otomatis jika tanggal lewat
    for log in logs:
        if log.next_schedule_date and log.next_schedule_date <= today and log.status == "Aman":
            log.status = "Kritis"
            is_changed = True
            
    if is_changed:
        db.commit() # Simpan perubahan status ke database
        
    return logs

def create_maintenance(db: Session, data: MaintenanceCreate):
    new_item = MaintenanceLog(**data.model_dump())
    db.add(new_item); db.commit(); db.refresh(new_item)
    return new_item

def delete_maintenance(db: Session, item_id: int):
    item = db.query(MaintenanceLog).filter(MaintenanceLog.id == item_id).first()
    if item: db.delete(item); db.commit()
    return {"message": "Jadwal maintenance dihapus."}


# ==========================================
# 4. STATISTIK DASHBOARD DINAMIS
# ==========================================
def get_dashboard_stats(db: Session):
    total_assets = db.query(Asset).count()
    total_components = db.query(Component).count()
    active_ips = db.query(NetworkIP).filter(NetworkIP.status == "Aktif").count()

    # Periksa dan update status maintenance yang lewat jadwal secara otomatis
    all_maintenance = get_all_maintenance(db)
    pending_maintenance = sum(1 for m in all_maintenance if m.status == "Kritis")

    # Distribusi Status Penggunaan Aset (Doughnut Chart)
    status_query = (
        db.query(Asset.status, func.count(Asset.id)).group_by(Asset.status).all()
    )
    if status_query:
        status_labels = [row[0] for row in status_query]
        status_data = [row[1] for row in status_query]
    else:
        status_labels = ["Digunakan", "Tersedia", "Rusak"]
        status_data = [0, 0, 0]

    # Distribusi Kategori Perangkat (Bar Chart)
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
