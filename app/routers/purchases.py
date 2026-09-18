from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
import uuid
import shutil
from pathlib import Path

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.domain import Purchase, Asset, User
from app.models.schemas.purchase import PurchaseResponse

router = APIRouter(prefix="/api/purchases", tags=["Purchases"])


# ==========================================
# POST — Tambah Pembelian + Upload Nota
# ==========================================
@router.post("/", response_model=PurchaseResponse)
async def create_purchase(
    # Multipart/Form-Data agar bisa menerima file sekaligus data teks
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
    # 1. Kalkulasi total di sisi server — cegah manipulasi dari frontend
    total_price = unit_price * quantity
    file_path = None

    # 2. Sanitisasi & Penyimpanan File (Anti-Directory Traversal)
    if invoice_file and invoice_file.filename:
        ext = invoice_file.filename.split(".")[-1].lower()
        if ext not in ["pdf", "jpg", "jpeg", "png"]:
            raise HTTPException(
                status_code=400,
                detail="Hanya ekstensi PDF, JPG, JPEG, dan PNG yang diizinkan.",
            )

        # Folder dinamis berbasis waktu: static/uploads/invoices/YYYY/MM
        year_month = datetime.now().strftime("%Y/%m")
        upload_dir = Path(f"static/uploads/invoices/{year_month}")
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Rename otomatis INV-YYYYMMDD-UUID — kebal overwrite & path traversal
        safe_filename = f"INV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}.{ext}"
        file_location = upload_dir / safe_filename

        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(invoice_file.file, buffer)

        # Path relatif untuk diakses via web browser (/static/...)
        file_path = f"/static/uploads/invoices/{year_month}/{safe_filename}"

    # 3. Simpan record pembelian ke MariaDB
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
    )
    db.add(new_purchase)
    db.flush()  # Dapatkan new_purchase.id sebelum commit penuh

    # 4. ERP Auto-Loop: Generate Aset per Unit yang Dibeli
    if auto_add_asset:
        # Beli 5 Mouse → sistem buat 5 baris Aset terpisah di Inventaris
        for i in range(quantity):
            asset_name = f"{item_name} #{i + 1}" if quantity > 1 else item_name
            new_asset = Asset(
                nama=asset_name,
                kelompok=category or "Lain-lain",
                status="Tersedia",
                kepemilikan="XML",         # Default kepemilikan perusahaan
                lokasi="Gudang IT",        # Akan dipindah saat distribusi
                digunakan_oleh=None,
                tanggal_masuk=purchase_date,
            )
            db.add(new_asset)

    db.commit()
    db.refresh(new_purchase)
    return new_purchase


# ==========================================
# GET — Ambil Semua Riwayat Pembelian
# ==========================================
@router.get("/", response_model=List[PurchaseResponse])
def get_purchases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Purchase).order_by(Purchase.purchase_date.desc()).all()


# ==========================================
# DELETE — Hapus Record + Hancurkan File Fisik
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

    # Auto-Garbage Collection: hancurkan file fisik agar tidak jadi zombie di disk
    if purchase.file_path:
        physical_file = Path(purchase.file_path.lstrip("/"))
        if physical_file.exists() and physical_file.is_file():
            physical_file.unlink()

    db.delete(purchase)
    db.commit()
    return {"message": "Data pembelian beserta file nota berhasil dihancurkan."}
