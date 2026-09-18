from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
from datetime import datetime
import shutil

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.domain import Purchase, Asset, User
from app.models.schemas.purchase import PurchaseResponse

router = APIRouter(prefix="/api/purchases", tags=["Purchases"])

# Direktori Induk Penyimpanan Nota — dibuat otomatis saat startup
UPLOAD_DIR = "static/uploads/invoices"


# ==========================================
# GET — Ambil Semua Riwayat Pembelian
# ==========================================
@router.get("/", response_model=List[PurchaseResponse])
def get_purchases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Purchase).order_by(Purchase.id.desc()).all()


# ==========================================
# POST — Tambah Pembelian Baru + Upload Nota
# ==========================================
@router.post("/", response_model=PurchaseResponse)
async def create_purchase(
    item_name: str = Form(...),
    vendor: Optional[str] = Form(None),
    unit_price: float = Form(...),
    quantity: int = Form(...),
    total_price: float = Form(...),
    purchase_date: str = Form(...),          # Format: YYYY-MM-DD
    category: Optional[str] = Form(None),    # Perangkat Keras, Lisensi, dll.
    description: Optional[str] = Form(None),
    auto_create_asset: bool = Form(False),   # Saklar "Bridge ke Inventaris"
    invoice_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_path = None

    # ── 1. PENANGANAN FILE UPLOAD ──────────────────────────────────────────
    if invoice_file and invoice_file.filename:
        allowed_extensions = [".jpg", ".jpeg", ".png", ".pdf"]
        ext = os.path.splitext(invoice_file.filename)[1].lower()

        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail="Ekstensi file tidak diizinkan. Gunakan JPG, PNG, atau PDF.",
            )

        # Sub-folder dinamis YYYY/MM — mencegah bottleneck I/O saat file ribuan
        now = datetime.now()
        year_month = now.strftime("%Y/%m")
        save_dir = os.path.join(UPLOAD_DIR, year_month)
        os.makedirs(save_dir, exist_ok=True)

        # Rename otomatis dengan UUID — keamanan & anti-collision
        unique_filename = f"INV-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}{ext}"
        physical_path = os.path.join(save_dir, unique_filename)

        with open(physical_path, "wb") as buffer:
            shutil.copyfileobj(invoice_file.file, buffer)

        # Path relatif yang disimpan di DB (dapat diakses via /static/...)
        file_path = f"/{UPLOAD_DIR}/{year_month}/{unique_filename}"

    # ── 2. PARSING TANGGAL ────────────────────────────────────────────────
    try:
        parsed_date = datetime.strptime(purchase_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Format tanggal salah. Gunakan YYYY-MM-DD.",
        )

    # ── 3. SIMPAN DATA KE MARIADB ─────────────────────────────────────────
    new_purchase = Purchase(
        item_name=item_name,
        vendor=vendor,
        unit_price=unit_price,
        quantity=quantity,
        total_price=total_price,
        purchase_date=parsed_date,
        category=category,
        description=description,
        file_path=file_path,
        created_by=current_user.id,
    )
    db.add(new_purchase)
    db.commit()
    db.refresh(new_purchase)

    # ── 4. ENTERPRISE BRIDGE: AUTO-GENERATE ASET ─────────────────────────
    # Jika saklar aktif, buat 1 record aset per unit yang dibeli
    if auto_create_asset:
        for _ in range(quantity):
            new_asset = Asset(
                nama=item_name,
                kelompok=category or "Uncategorized",
                status="Draft",           # IT Review nanti (lengkapi SN, Mac, dll.)
                tanggal_masuk=parsed_date,
                kepemilikan="XML",        # Default kepemilikan perusahaan
                lokasi="Gudang IT",       # Default lokasi sebelum didistribusikan
                digunakan_oleh=None,
            )
            db.add(new_asset)
        db.commit()

    return new_purchase


# ==========================================
# DELETE — Hapus Pembelian + Hancurkan File Fisik
# ==========================================
@router.delete("/{purchase_id}")
def delete_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "Super Admin":
        raise HTTPException(
            status_code=403,
            detail="Hanya Super Admin yang dapat menghapus data pembelian.",
        )

    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Data pembelian tidak ditemukan.")

    # Hancurkan file fisik di server — cegah orphaned files / storage bloat
    if purchase.file_path:
        # Strip leading "/" agar menjadi relative path yang valid
        file_to_delete = purchase.file_path.lstrip("/")
        if os.path.exists(file_to_delete):
            os.remove(file_to_delete)

    db.delete(purchase)
    db.commit()
    return {"message": "Data pembelian dan file nota berhasil dihapus permanen."}
