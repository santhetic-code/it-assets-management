from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
import uuid
import shutil
from pathlib import Path

from app.core.database import get_db
from app.core.deps import get_audit_logger, get_current_user, require_super_admin
from app.core.security import verify_csrf_token
from app.models.domain import Purchase, Asset, SystemLogs, User, get_utc_now
from app.models.schemas.purchase import PurchaseResponse

router = APIRouter(prefix="/api/purchases", tags=["Purchases"])


# ==========================================
# POST — Tambah Pembelian + Upload Nota
# ==========================================
@router.post("/", response_model=PurchaseResponse, dependencies=[Depends(verify_csrf_token)])
async def create_purchase(
    item_name: str = Form(...),
    vendor: Optional[str] = Form(None),
    unit_price: float = Form(...),
    quantity: int = Form(...),
    purchase_date: date = Form(...),
    category: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    auto_add_asset: bool = Form(False),
    invoice_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Kalkulasi total di sisi server
    total_price = unit_price * quantity
    file_path = None

    # 2. Sanitisasi & Penyimpanan File
    if invoice_file and invoice_file.filename:
        ext = invoice_file.filename.split(".")[-1].lower()
        if ext not in ["pdf", "jpg", "jpeg", "png"]:
            raise HTTPException(
                status_code=400,
                detail="Hanya ekstensi PDF, JPG, JPEG, dan PNG yang diizinkan.",
            )

        year_month = datetime.now().strftime("%Y/%m")
        upload_dir = Path(f"static/uploads/invoices/{year_month}")
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = f"INV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}.{ext}"
        file_location = upload_dir / safe_filename

        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(invoice_file.file, buffer)

        file_path = f"/static/uploads/invoices/{year_month}/{safe_filename}"

    try:
        # 3. Simpan record pembelian
        new_purchase = Purchase(
            item_name=item_name,
            vendor=vendor,
            unit_price=unit_price,
            quantity=quantity,
            total_price=total_price,
            purchase_date=purchase_date,
            category=category,
            description=description,
            file_path=file_path,
            created_by=current_user.id,
            is_deleted=False,
        )
        db.add(new_purchase)
        db.flush()

        # 4. ERP Auto-Loop: Generate Aset per Unit yang Dibeli
        if auto_add_asset:
            for i in range(quantity):
                asset_name = f"{item_name} #{i + 1}" if quantity > 1 else item_name
                new_asset = Asset(
                    nama=asset_name,
                    kelompok=category or "Lain-lain",
                    status="Tersedia",
                    kepemilikan="XML",
                    lokasi="Gudang IT",
                    digunakan_oleh=None,
                    tanggal_masuk=purchase_date,
                    is_deleted=False,
                )
                db.add(new_asset)

        db.commit()
        db.refresh(new_purchase)
        return new_purchase
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal mencatat data pembelian: {str(e)}")


# ==========================================
# GET — Ambil Semua Riwayat Pembelian Aktif
# ==========================================
@router.get("/", response_model=List[PurchaseResponse])
def get_purchases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Purchase)
        .filter(Purchase.is_deleted == False)
        .order_by(Purchase.purchase_date.desc())
        .all()
    )


# ==========================================
# DELETE — Soft Delete Data Pembelian (Preservasi Nota & Audit)
# ==========================================
@router.delete("/{purchase_id}", dependencies=[Depends(require_super_admin), Depends(verify_csrf_token)])
def delete_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_info: dict = Depends(get_audit_logger),
):
    purchase = db.query(Purchase).filter(
        Purchase.id == purchase_id,
        Purchase.is_deleted == False
    ).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Data pembelian tidak ditemukan.")

    item_name = purchase.item_name
    try:
        # Soft delete: tandai status tanpa menghapus baris dan file fisik
        purchase.is_deleted = True
        purchase.deleted_at = get_utc_now()
        purchase.deleted_by = current_user.id

        # Rekam forensik ke SystemLogs
        log_entry = SystemLogs(
            user_id=current_user.id,
            action=f"SOFT_DELETE: Menghapus data transaksi pembelian '{item_name}' (ID: {purchase_id})",
            entity="Purchase",
            entity_id=purchase_id,
            ip_address=audit_info.get("ip", "Unknown"),
            timestamp=get_utc_now(),
        )
        db.add(log_entry)

        db.commit()
        return {"message": f"Data pembelian '{item_name}' berhasil dinonaktifkan (Soft Delete) dan dicatat di Audit Trail."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menghapus data pembelian: {str(e)}")

