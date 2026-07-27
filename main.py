import datetime
import io
import os
from datetime import datetime as dt_datetime
from datetime import timezone
from typing import Annotated

import bcrypt
import pandas as pd
import qrcode
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    Body,
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import database
import models
import security

load_dotenv()

# Master Key Statis untuk Brankas (Membaca dari .env jika di production)
vault_env = os.getenv("VAULT_KEY", "fallback_key_pastikan_diset_di_env_base64=")
VAULT_KEY = vault_env.encode() if isinstance(vault_env, str) else vault_env
cipher_suite = Fernet(VAULT_KEY)

# ==========================================
# 1. INISIALISASI & KONFIGURASI DASAR
# ==========================================
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="ITAM Backend")

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="views")

# Dependency Database
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def parse_date(date_str):
    if not date_str:
        return None
    if isinstance(date_str, (datetime.date, datetime.datetime)):
        return date_str
    try:
        if 'T' in date_str:
            return datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M").date() # noqa: DTZ007
        elif ' ' in date_str:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M").date() # noqa: DTZ007
        return datetime.date.fromisoformat(date_str)
    except Exception: # noqa: BLE001
        try:
            return datetime.datetime.fromisoformat(date_str).date()
        except Exception: # noqa: BLE001
            return None


# ==========================================
# 2. SISTEM KEAMANAN & OTORISASI (RBAC)
# ==========================================
class NotAuthenticatedException(Exception):
    pass

@app.exception_handler(NotAuthenticatedException)
def auth_exception_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url="/login", status_code=303)

# 1. PENJAGA PINTU UTAMA (Mengenali Identitas Lengkap)
def get_current_user(request: Request, db: Annotated[Session, Depends(get_db)], itam_session: Annotated[str | None, Cookie()] = None):
    if not itam_session:
        raise NotAuthenticatedException()
        
    # Perbaikan SE: Tangkap error dari JWT agar diarahkan ke halaman login, bukan layar putih
    try:
        username = security.verify_jwt_token(itam_session)
    except HTTPException:
        raise NotAuthenticatedException()
        
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise NotAuthenticatedException()
    return user

# 2. PENGECEK JABATAN SUPER ADMIN (Hanya untuk fitur bahaya seperti Hapus Akun)
def require_super_admin(current_user: Annotated[models.User, Depends(get_current_user)]):
    if current_user.role != "Super Admin":
        raise HTTPException(status_code=403, detail="Akses Ditolak: Fitur ini hanya untuk Super Admin.")
    return current_user

# 3. PENGECEK JABATAN STAFF/ADMIN (Untuk fitur Tambah/Edit Data)
def require_staff_or_admin(current_user: Annotated[models.User, Depends(get_current_user)]):
    if current_user.role not in ["Super Admin", "Staff IT"]:
        raise HTTPException(status_code=403, detail="Akses Ditolak: Anda adalah Viewer, hanya diizinkan melihat data.")
    return current_user


# ==========================================
# 2.B MIDDLEWARE: AUDIT TRAIL LOGGING
# ==========================================
def log_system_activity(db: Session, username: str, action: str, endpoint: str, ip_address: str):
    """
    Fungsi eksekusi latar belakang untuk menulis ke database.
    Tidak akan memperlambat respon API kepada pengguna.
    """
    try:
        new_log = models.SystemLogs(
            user_id=username,
            action=action,
            endpoint=endpoint,
            ip_address=ip_address
        )
        db.add(new_log)
        db.commit()
    except Exception as e:  # noqa: BLE001
        # Jika log gagal ditulis, kita tidak ingin aplikasi crash
        print(f"CRITICAL ERROR [Audit Log]: Gagal menulis log untuk {username} - {e}")

async def audit_logger(
    request: Request, 
    background_tasks: BackgroundTasks, 
    db: Annotated[Session, Depends(get_db)], 
    itam_session: str | None = Cookie(None)
):
    """
    Middleware Dependency yang akan memonitor transaksi.
    """
    # 1. Pastikan yang melakukan transaksi adalah user yang memiliki sesi
    username = "System/Unknown"
    if itam_session:
        try:
            username = security.verify_jwt_token(itam_session)
        except HTTPException:
            pass # Biarkan lolos di sini, karena akan diblokir oleh verify_csrf_token atau get_current_user

    # 2. Ekstrak rincian transaksi
    action_method = request.method
    endpoint_path = request.url.path
    client_ip = request.client.host if request.client else "Unknown IP"
    
    # 3. Lempar eksekusi insert database ke Background Task
    background_tasks.add_task(log_system_activity, db, username, action_method, endpoint_path, client_ip)

# ==========================================
# 3. AUTENTIKASI (LOGIN & LOGOUT)
# ==========================================
@app.get("/login")
def login_page(request: Request):
    csrf_token = security.generate_csrf_token()
    response = templates.TemplateResponse(request=request, name="login.html", context={"request": request, "csrf_token": csrf_token})
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
    return response

@app.post("/login", dependencies=[Depends(security.verify_csrf_token)])
def login_submit(
    request: Request,
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    db: Annotated[Session, Depends(database.get_db)]
):
    # --- SEEDING OTOMATIS (Hanya untuk testing awal) ---
    if db.query(models.User).count() == 0:
        default_hashed_pw = hash_password("admin123")
        new_admin = models.User(username="admin", password_hash=default_hashed_pw)
        db.add(new_admin)
        db.commit()
    # ---------------------------------------------------

    user = db.query(models.User).filter(models.User.username == username).first()
    
    if not user or not verify_password(password, user.password_hash):
        csrf_token = security.generate_csrf_token()
        response = templates.TemplateResponse(
            request=request, 
            name="login.html", 
            context={"request": request, "error_msg": "Username atau password salah!", "csrf_token": csrf_token}
        )
        response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
        return response
    
    # Generate JWT
    access_token = security.create_access_token(data={"sub": user.username})
    
    response = RedirectResponse(url="/", status_code=302)
    # Atribut Keamanan Super Ketat dari CSE
    response.set_cookie(
        key="itam_session", value=access_token, 
        httponly=True, secure=False, samesite="strict"
    )
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("itam_session")
    response.delete_cookie("csrf_token")
    return response


# ==========================================
# 4. ENDPOINT HALAMAN WEB (DILINDUNGI)
# ==========================================
@app.get("/")
def read_dashboard(
    request: Request, 
    db: Annotated[Session, Depends(database.get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)]
):
    assets = db.query(models.Asset).all()
    components = db.query(models.Component).all()
    ips = db.query(models.NetworkIP).all()
    maintenances = db.query(models.MaintenanceLog).all()

    total_assets = len(assets)
    total_components = len(components)
    active_ips = sum(1 for ip in ips if ip.status == 'Aktif')
    pending_maintenance = sum(1 for m in maintenances if m.status in ['Perlu Dicek', 'Kritis'])

    kategori_counts = {}
    for a in assets:
        cat = a.category if a.category else "Lainnya"
        kategori_counts[cat] = kategori_counts.get(cat, 0) + 1

    status_counts = {}
    for a in assets:
        st = a.usage_status if a.usage_status else "Lainnya"
        status_counts[st] = status_counts.get(st, 0) + 1

    csrf_token = security.generate_csrf_token()
    response = templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={
            "request": request,
            "assets": assets,
            "total_assets": total_assets,
            "total_components": total_components,
            "active_ips": active_ips,
            "pending_maintenance": pending_maintenance,
            "bar_labels": list(kategori_counts.keys()),
            "bar_data": list(kategori_counts.values()),
            "status_labels": list(status_counts.keys()),
            "status_data": list(status_counts.values()),

            "current_user": current_user,
            "csrf_token": csrf_token
        }
    )
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
    return response

@app.get("/it-notes")
def read_it_notes(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[str, Depends(get_current_user)],
    search: str | None = None
):
    query = db.query(models.Asset)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            models.Asset.name.ilike(search_term) |
            models.Asset.asset_tag.ilike(search_term) |
            models.Asset.serial_number.ilike(search_term) |
            models.Asset.assigned_to.ilike(search_term)
        )
    assets = query.all()
    csrf_token = security.generate_csrf_token()
    response = templates.TemplateResponse(request=request, name="it_notes.html", context={"title": "Catatan IT", "assets": assets, "search": search, "csrf_token": csrf_token})
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
    return response

@app.get("/network")
def read_network_web(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[str, Depends(get_current_user)],
    search: str | None = None
):
    query = db.query(models.NetworkIP)
    if search:
        query = query.filter(
            models.NetworkIP.ip_address.ilike(f"%{search}%") |
            models.NetworkIP.status.ilike(f"%{search}%") |
            models.NetworkIP.ip_type.ilike(f"%{search}%") |
            models.NetworkIP.assigned_to.ilike(f"%{search}%")
        )
    ips = query.all()
    csrf_token = security.generate_csrf_token()
    response = templates.TemplateResponse(request=request, name="ips.html", context={"title": "Manajemen IP", "ips": ips, "search": search, "csrf_token": csrf_token})
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
    return response

@app.get("/vault")
def read_credentials_vault(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[str, Depends(get_current_user)],
    search: str | None = None
):
    query = db.query(models.Credential)
    if search:
        query = query.filter(
            models.Credential.title.ilike(f"%{search}%") |
            models.Credential.username.ilike(f"%{search}%") |
            models.Credential.service_type.ilike(f"%{search}%") |
            models.Credential.division.ilike(f"%{search}%")
        )
    credentials = query.all()
    csrf_token = security.generate_csrf_token()
    response = templates.TemplateResponse(request=request, name="credentials.html", context={"title": "Brankas Kredensial", "credentials": credentials, "search": search, "csrf_token": csrf_token})
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
    return response

@app.get("/purchase-records")
def read_purchases_web(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[str, Depends(get_current_user)],
    search: str | None = None
):
    query = db.query(models.Purchase)
    if search:
        query = query.filter(
            models.Purchase.item_name.ilike(f"%{search}%") |
            models.Purchase.vendor.ilike(f"%{search}%") |
            models.Purchase.buyer_name.ilike(f"%{search}%")
        )
    purchases = query.all()
    csrf_token = security.generate_csrf_token()
    response = templates.TemplateResponse(request=request, name="purchases.html", context={"title": "Rekap Pembelian", "purchases": purchases, "search": search, "csrf_token": csrf_token})
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
    return response

@app.get("/hardware-components")
def read_components_web(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[str, Depends(get_current_user)],
    search: str | None = None
):
    query = db.query(models.Component)
    if search:
        query = query.filter(
            models.Component.assigned_to.ilike(f"%{search}%") |
            models.Component.os_name.ilike(f"%{search}%") |
            models.Component.processor_spec.ilike(f"%{search}%") |
            models.Component.mainboard_spec.ilike(f"%{search}%") |
            models.Component.ram_spec.ilike(f"%{search}%") |
            models.Component.vga_spec.ilike(f"%{search}%") |
            models.Component.storage_spec.ilike(f"%{search}%") |
            models.Component.pc_category.ilike(f"%{search}%") |
            models.Component.location.ilike(f"%{search}%")
        )
    components = query.all()
    csrf_token = security.generate_csrf_token()
    response = templates.TemplateResponse(request=request, name="components.html", context={"title": "Komponen Internal", "components": components, "search": search, "csrf_token": csrf_token})
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
    return response

@app.get("/maintenance-logs")
def read_maintenance(
    request: Request, 
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[str, Depends(get_current_user)]
):
    logs = db.query(models.MaintenanceLog).all()
    all_assets = db.query(models.Asset).all() 
    csrf_token = security.generate_csrf_token()
    response = templates.TemplateResponse(
        request=request,
        name="maintenance.html", 
        context={
            "request": request, 
            "maintenance_logs": logs,
            "assets": all_assets,
            "csrf_token": csrf_token
        }
    )
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
    return response

@app.get("/account")
def read_account(
    request: Request, 
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[str, Depends(get_current_user)] # Penjaga pintu tetap dipasang
):
    # Ambil data semua user dari database untuk ditampilkan di tabel Manajemen Akun
    users = db.query(models.User).all()
    
    csrf_token = security.generate_csrf_token()
    response = templates.TemplateResponse(
        request=request,
        name="account.html", 
        context={
            "request": request,
            "title": "Akun & Keamanan",
            "users": users,
            "current_user": current_user,
            "csrf_token": csrf_token
        }
    )
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
    return response

@app.get("/system-logs")
def read_system_logs(
    request: Request, 
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(require_super_admin)] # Hanya Super Admin
):
    # Mengambil 500 log terbaru secara menurun (descending)
    logs = db.query(models.SystemLogs).order_by(models.SystemLogs.timestamp.desc()).limit(500).all()
    return templates.TemplateResponse(
        request=request, 
        name="logs.html", 
        context={"request": request, "logs": logs, "current_user": current_user}
    )


# ==========================================
# 5. API ENDPOINTS (MANAJEMEN DATA)
# ==========================================
# ==========================================
# ENDPOINT: GENERATOR QR CODE FISIK
# ==========================================
@app.get("/api/qr/{asset_tag}")
def generate_qr_code(asset_tag: str):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(asset_tag)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")

# ==========================================
# ENDPOINT: DOWNLOAD TEMPLATE IMPORT EXCEL
# ==========================================
@app.get("/assets/template/")
def download_asset_template():
    df = pd.DataFrame(columns=["Tag Aset", "Nama Perangkat", "Kategori", "SN", "Pengguna", "Lokasi"])
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template Import Aset')
    output.seek(0)

    headers = {
        'Content-Disposition': 'attachment; filename="Template_Import_Aset.xlsx"'
    }
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.post("/assets/", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def create_asset(asset_data: Annotated[dict, Body(...)], db: Annotated[Session, Depends(get_db)]):
    new_asset = models.Asset(
        asset_tag=asset_data.get("asset_tag"),
        name=asset_data.get("name"),
        category=asset_data.get("category"),
        serial_number=asset_data.get("serial_number"),
        ownership=asset_data.get("ownership"),
        location=asset_data.get("location"),
        condition=asset_data.get("condition", "Baru"),
        usage_status=asset_data.get("usage_status", "Digunakan"),
        assigned_to=asset_data.get("assigned_to"),
        notes=asset_data.get("notes")
    )
    db.add(new_asset)
    db.commit()
    return {"message": "Aset berhasil ditambahkan"}

@app.put("/assets/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def update_asset(id: int, asset_data: Annotated[dict, Body(...)], db: Annotated[Session, Depends(get_db)]):
    db_asset = db.query(models.Asset).filter(models.Asset.id == id).first()
    if not db_asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    for key, value in asset_data.items():
        setattr(db_asset, key, value)
    db.commit()
    return {"message": "Aset berhasil diperbarui"}

@app.delete("/assets/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def delete_asset(id: int, db: Annotated[Session, Depends(get_db)]):
    db_asset = db.query(models.Asset).filter(models.Asset.id == id).first()
    if not db_asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    db.delete(db_asset)
    db.commit()
    return {"message": "Aset berhasil dihapus"}

@app.post("/assets/import/", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
async def import_assets(request: Request, db: Annotated[Session, Depends(get_db)]):
    try:
        # 1. Ambil form langsung dari request (Bebas dari bentrokan Middleware)
        form = await request.form()
        file = form.get("file")
        
        if not file:
            raise HTTPException(status_code=400, detail="File tidak ditemukan dalam form")

        # 2. Kembalikan kursor file ke posisi awal (0)
        await file.seek(0)
        contents = await file.read()

        filename = (file.filename or "").lower()
        if filename.endswith('.csv'):
            # Modifikasi: Tambahkan .fillna("") untuk menangani sel kosong
            df = pd.read_csv(io.BytesIO(contents)).fillna("")
        elif filename.endswith(('.xls', '.xlsx')):
            # Modifikasi: Tambahkan .fillna("") untuk menangani sel kosong
            df = pd.read_excel(io.BytesIO(contents)).fillna("")
        else:
            raise HTTPException(status_code=400, detail="Format harus CSV atau Excel (.xlsx)")

        # --- PERBAIKAN SE KODE DIMULAI DARI SINI ---
        if "Tag Aset" not in df.columns:
            raise HTTPException(status_code=400, detail="Gagal: Kolom 'Tag Aset' tidak ditemukan! Pastikan Anda menggunakan format Template Excel yang benar.")

        df = df[df['Tag Aset'].astype(str).str.strip() != ""]

        df = security.sanitize_csv_dataframe(df)
        # --- PERBAIKAN SE KODE SELESAI ---

        for _, row in df.iterrows():
            new_asset = models.Asset(
                asset_tag=str(row.get('Tag Aset', '')),
                name=str(row.get('Nama Perangkat', '')),
                category=str(row.get('Kategori', 'Lainnya')),
                serial_number=str(row.get('SN', '')),
                assigned_to=str(row.get('Pengguna', '')),
                location=str(row.get('Lokasi', '')),
                condition="Baru",
                usage_status="Digunakan"
            )
            db.add(new_asset)

        db.commit()
        return {"message": "Data massal berhasil diimpor!"}
        
    except Exception as e:  # noqa: BLE001
        db.rollback()
        # Mencetak error asli ke terminal agar kita tahu pasti jika ada kesalahan lain
        print(f"\n[CRITICAL ERROR IMPORT] -> {e!s}\n")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/ips/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def delete_ip(id: int, db: Annotated[Session, Depends(get_db)]):
    db_ip = db.query(models.NetworkIP).filter(models.NetworkIP.id == id).first()
    if not db_ip:
        raise HTTPException(status_code=404, detail="IP tidak ditemukan")
    db.delete(db_ip)
    db.commit()
    return {"message": "IP berhasil dihapus"}

@app.post("/credentials/", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def create_credential(cred_data: Annotated[dict, Body(...)], db: Annotated[Session, Depends(get_db)]):
    if cred_data.get("asset_id"):
        asset_exists = db.query(models.Asset).filter(models.Asset.id == cred_data["asset_id"]).first()
        if not asset_exists:
            raise HTTPException(status_code=400, detail="ID Aset tidak ditemukan")
    # Encrypt password before saving
    encrypted_pwd = None
    if cred_data.get("password_hash"):
        encrypted_pwd = cipher_suite.encrypt(cred_data.get("password_hash").encode()).decode()

    new_cred = models.Credential(
        service_type=cred_data.get("service_type"),
        title=cred_data.get("title"),
        access_url_or_ip=cred_data.get("access_url_or_ip"),
        username=cred_data.get("username"),
        password_hash=encrypted_pwd,
        division=cred_data.get("division"),
        asset_id=cred_data.get("asset_id")
    )
    db.add(new_cred)
    db.commit()
    return {"message": "Kredensial berhasil disimpan"}

@app.put("/credentials/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def update_credential(id: int, cred_data: Annotated[dict, Body(...)], db: Annotated[Session, Depends(get_db)]):
    db_cred = db.query(models.Credential).filter(models.Credential.id == id).first()
    if not db_cred:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan")
    if cred_data.get("asset_id"):
        asset_exists = db.query(models.Asset).filter(models.Asset.id == cred_data["asset_id"]).first()
        if not asset_exists:
            raise HTTPException(status_code=400, detail="ID Aset tidak ditemukan")
    # If password provided, encrypt it before updating
    if cred_data.get("password_hash"):
        cred_data["password_hash"] = cipher_suite.encrypt(cred_data.get("password_hash").encode()).decode()
    for key, value in cred_data.items():
        setattr(db_cred, key, value)
    db.commit()
    return {"message": "Kredensial berhasil diperbarui"}

@app.delete("/credentials/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def delete_credential(id: int, db: Annotated[Session, Depends(get_db)]):
    db_cred = db.query(models.Credential).filter(models.Credential.id == id).first()
    if not db_cred:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan")
    db.delete(db_cred)
    db.commit()
    return {"message": "Kredensial berhasil dihapus"}


@app.get("/api/vault/reveal/{id}")
def reveal_credential(id: int, db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(get_current_user)]):
    cred = db.query(models.Credential).filter(models.Credential.id == id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan")
    
    # Toleransi untuk data lama (Plaintext) vs data baru (AES)
    try:
        decrypted_pwd = cipher_suite.decrypt(cred.password_hash.encode()).decode() if cred.password_hash else None
    except Exception: # noqa: BLE001
        # Jika proses dekripsi gagal, berarti ini adalah sandi lama sebelum sistem enkripsi diterapkan
        decrypted_pwd = cred.password_hash

    return {"password": decrypted_pwd}

@app.post("/purchases/", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
async def create_purchase(
    item_name: Annotated[str, Form(...)],
    vendor: Annotated[str, Form(...)],
    purchase_date: Annotated[str, Form(...)],
    price_per_item: Annotated[float, Form(...)],
    quantity: Annotated[int, Form(...)],
    buyer_name: Annotated[str, Form(...)],
    db: Annotated[Session, Depends(get_db)], # 👈 PINDAHKAN db KE SINI
    invoice_link: Annotated[str | None, Form()] = None,
    nota_file: Annotated[UploadFile | None, File()] = None
):
    total_price = price_per_item * quantity
    p_date = parse_date(purchase_date) or dt_datetime.now(timezone.utc).date()
    final_link = invoice_link

    if nota_file and nota_file.filename:
        # Eksekusi Sprint 2: Batasi ekstensi (termasuk PDF untuk nota)
        allowed_exts = ["jpg", "jpeg", "png", "pdf"]
        
        # Reset file stream in case middleware/readers consumed it earlier
        await nota_file.seek(0)
        # Eksekusi pengamanan upload nota
        final_link = await security.secure_save_file(nota_file, allowed_exts, "static/uploads")

    new_purchase = models.Purchase(
        purchase_date=p_date,
        item_name=item_name,
        vendor=vendor,
        price_per_item=price_per_item,
        quantity=quantity,
        total_price=total_price,
        buyer_name=buyer_name,
        invoice_link=final_link 
    )
    db.add(new_purchase)
    db.commit()
    return {"message": "Pembelian dan nota berhasil dicatat dengan aman"}

@app.put("/purchases/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def update_purchase(id: int, purchase_data: Annotated[dict, Body(...)], db: Annotated[Session, Depends(get_db)]):
    db_purchase = db.query(models.Purchase).filter(models.Purchase.id == id).first()
    if not db_purchase:
        raise HTTPException(status_code=404, detail="Pembelian tidak ditemukan")
    
    if "purchase_date" in purchase_data:
        purchase_data["purchase_date"] = parse_date(purchase_data["purchase_date"])

    for key, value in purchase_data.items():
        setattr(db_purchase, key, value)
        
    price_per_item = float(db_purchase.price_per_item or 0.0)
    quantity = int(db_purchase.quantity or 1)
    db_purchase.total_price = price_per_item * quantity
    
    db.commit()
    return {"message": "Pembelian berhasil diperbarui"}

@app.delete("/purchases/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def delete_purchase(id: int, db: Annotated[Session, Depends(get_db)]):
    db_purchase = db.query(models.Purchase).filter(models.Purchase.id == id).first()
    if not db_purchase:
        raise HTTPException(status_code=404, detail="Pembelian tidak ditemukan")
    db.delete(db_purchase)
    db.commit()
    return {"message": "Pembelian berhasil dihapus"}

@app.post("/components/", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def create_component(comp_data: Annotated[dict, Body(...)], db: Annotated[Session, Depends(get_db)]):
    if comp_data.get("asset_id"):
        asset_exists = db.query(models.Asset).filter(models.Asset.id == comp_data["asset_id"]).first()
        if not asset_exists:
            raise HTTPException(status_code=400, detail="ID Aset tidak ditemukan")
    new_comp = models.Component(
        asset_id=comp_data.get("asset_id"),
        assigned_to=comp_data.get("assigned_to"),
        os_name=comp_data.get("os_name"),
        processor_spec=comp_data.get("processor_spec"),
        mainboard_spec=comp_data.get("mainboard_spec"),
        ram_spec=comp_data.get("ram_spec"),
        vga_spec=comp_data.get("vga_spec"),
        storage_spec=comp_data.get("storage_spec"),
        pc_category=comp_data.get("pc_category"),
        location=comp_data.get("location")
    )
    db.add(new_comp)
    db.commit()
    return {"message": "Komponen berhasil ditambahkan"}

@app.put("/components/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def update_component(id: int, comp_data: Annotated[dict, Body(...)], db: Annotated[Session, Depends(get_db)]):
    db_comp = db.query(models.Component).filter(models.Component.id == id).first()
    if not db_comp:
        raise HTTPException(status_code=404, detail="Komponen tidak ditemukan")
    if comp_data.get("asset_id"):
        asset_exists = db.query(models.Asset).filter(models.Asset.id == comp_data["asset_id"]).first()
        if not asset_exists:
            raise HTTPException(status_code=400, detail="ID Aset tidak ditemukan")
    for key, value in comp_data.items():
        setattr(db_comp, key, value)
    db.commit()
    return {"message": "Komponen berhasil diperbarui"}

@app.delete("/components/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def delete_component(id: int, db: Annotated[Session, Depends(get_db)]):
    db_comp = db.query(models.Component).filter(models.Component.id == id).first()
    if not db_comp:
        raise HTTPException(status_code=404, detail="Komponen tidak ditemukan")
    db.delete(db_comp)
    db.commit()
    return {"message": "Komponen berhasil dihapus"}

@app.post("/maintenance/", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def create_maintenance(maint_data: Annotated[dict, Body(...)], db: Annotated[Session, Depends(get_db)]):
    if maint_data.get("asset_id"):
        asset_exists = db.query(models.Asset).filter(models.Asset.id == maint_data["asset_id"]).first()
        if not asset_exists:
            raise HTTPException(status_code=400, detail="ID Aset tidak ditemukan")
            
    last_maint = parse_date(maint_data.get("last_maintenance_date"))
    next_sched = parse_date(maint_data.get("next_schedule_date"))
    
    new_maint = models.MaintenanceLog(
        asset_id=maint_data.get("asset_id"),
        location_target=maint_data.get("location_target"),
        task_type=maint_data.get("task_type"),
        last_maintenance_date=last_maint,
        interval_months=int(maint_data.get("interval_months", 3)),
        next_schedule_date=next_sched,
        status=maint_data.get("status", "Aman")
    )
    db.add(new_maint)
    db.commit()
    return {"message": "Jadwal berhasil ditambahkan"}

@app.put("/maintenance/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def update_maintenance(id: int, maint_data: Annotated[dict, Body(...)], db: Annotated[Session, Depends(get_db)]):
    db_maint = db.query(models.MaintenanceLog).filter(models.MaintenanceLog.id == id).first()
    if not db_maint:
        raise HTTPException(status_code=404, detail="Jadwal pemeliharaan tidak ditemukan")
    if maint_data.get("asset_id"):
        asset_exists = db.query(models.Asset).filter(models.Asset.id == maint_data["asset_id"]).first()
        if not asset_exists:
            raise HTTPException(status_code=400, detail="ID Aset tidak ditemukan")
        
    if "last_maintenance_date" in maint_data:
        maint_data["last_maintenance_date"] = parse_date(maint_data["last_maintenance_date"])
    if "next_schedule_date" in maint_data:
        maint_data["next_schedule_date"] = parse_date(maint_data["next_schedule_date"])

    for key, value in maint_data.items():
        setattr(db_maint, key, value)
    db.commit()
    return {"message": "Jadwal pemeliharaan berhasil diperbarui"}

@app.delete("/maintenance/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def delete_maintenance(id: int, db: Annotated[Session, Depends(get_db)]):
    db_maint = db.query(models.MaintenanceLog).filter(models.MaintenanceLog.id == id).first()
    if not db_maint:
        raise HTTPException(status_code=404, detail="Jadwal pemeliharaan tidak ditemukan")
    db.delete(db_maint)
    db.commit()
    return {"message": "Jadwal pemeliharaan berhasil dihapus"}

@app.post("/health-reports/", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def create_health_report(health_data: Annotated[dict, Body(...)], db: Annotated[Session, Depends(get_db)]):
    if health_data.get("asset_id"):
        asset_exists = db.query(models.Asset).filter(models.Asset.id == health_data["asset_id"]).first()
        if not asset_exists:
            raise HTTPException(status_code=400, detail="ID Aset tidak ditemukan")
            
    c_date = parse_date(health_data.get("check_date")) or dt_datetime.now(timezone.utc).date()

    new_report = models.HealthMonitoring(
        asset_id=health_data.get("asset_id"),
        check_date=c_date,
        cpu_usage_percent=float(health_data["cpu_usage_percent"]) if health_data.get("cpu_usage_percent") is not None else None,
        memory_usage_percent=float(health_data["memory_usage_percent"]) if health_data.get("memory_usage_percent") is not None else None,
        disk_c_health=health_data.get("disk_c_health"),
        disk_c_free_gb=float(health_data["disk_c_free_gb"]) if health_data.get("disk_c_free_gb") is not None else None,
        disk_d_health=health_data.get("disk_d_health"),
        disk_d_free_gb=float(health_data["disk_d_free_gb"]) if health_data.get("disk_d_free_gb") is not None else None,
        status_alert=health_data.get("status_alert", "Aman")
    )
    db.add(new_report)
    db.commit()
    return {"message": "Laporan kesehatan berhasil disimpan"}

@app.put("/health-reports/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def update_health_report(id: int, health_data: Annotated[dict, Body(...)], db: Annotated[Session, Depends(get_db)]):
    db_report = db.query(models.HealthMonitoring).filter(models.HealthMonitoring.id == id).first()
    if not db_report:
        raise HTTPException(status_code=404, detail="Laporan kesehatan tidak ditemukan")
    if health_data.get("asset_id"):
        asset_exists = db.query(models.Asset).filter(models.Asset.id == health_data["asset_id"]).first()
        if not asset_exists:
            raise HTTPException(status_code=400, detail="ID Aset tidak ditemukan")
    
    if "check_date" in health_data:
        health_data["check_date"] = parse_date(health_data["check_date"])

    for key, value in health_data.items():
        setattr(db_report, key, value)
    db.commit()
    return {"message": "Laporan kesehatan berhasil diperbarui"}

@app.delete("/health-reports/{id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def delete_health_report(id: int, db: Annotated[Session, Depends(get_db)]):
    db_report = db.query(models.HealthMonitoring).filter(models.HealthMonitoring.id == id).first()
    if not db_report:
        raise HTTPException(status_code=404, detail="Laporan kesehatan tidak ditemukan")
    db.delete(db_report)
    db.commit()
    return {"message": "Laporan kesehatan berhasil dihapus"}

@app.post("/change-password", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def change_password(
    request: Request,
    old_password: Annotated[str, Form(...)],
    new_password: Annotated[str, Form(...)],
    confirm_password: Annotated[str, Form(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[str, Depends(get_current_user)] # Pastikan hanya user login yang bisa akses
):
    # 1. Ambil data user yang sedang login dari database
    user = db.query(models.User).filter(models.User.username == current_user.username).first()
    
    # Siapkan data users untuk dirender ulang ke halaman (karena tabel membutuhkannya)
    users = db.query(models.User).all()
    
    # 2. Validasi: Apakah kata sandi lama yang diketikkan BENAR?
    # (Di bagian error sandi lama salah)
    if not verify_password(old_password, user.password_hash):
        users = db.query(models.User).all()
        csrf_token = security.generate_csrf_token()
        response = templates.TemplateResponse(
            request=request,
            name="account.html",
            context={"request": request, "users": users, "error_msg": "Kata sandi lama tidak sesuai!", "current_user": current_user, "csrf_token": csrf_token}
        )
        response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
        return response
        
    # (Di bagian error sandi baru tidak cocok)
    if new_password != confirm_password:
        users = db.query(models.User).all()
        csrf_token = security.generate_csrf_token()
        response = templates.TemplateResponse(
            request=request,
            name="account.html",
            context={"request": request, "users": users, "error_msg": "Konfirmasi kata sandi baru tidak cocok!", "current_user": current_user, "csrf_token": csrf_token}
        )
        response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
        return response
    
    # 1. Enkripsi kata sandi yang baru
    hashed_password = hash_password(new_password)
    
    # 2. Timpa sandi lama dengan sandi yang baru
    user.password_hash = hashed_password
    
    # 3. Simpan permanen ke database
    db.commit()

    # (Di bagian sukses)
    users = db.query(models.User).all()
    csrf_token = security.generate_csrf_token()
    response = templates.TemplateResponse(
        request=request,
        name="account.html",
        context={"request": request, "users": users, "success_msg": "Kata sandi berhasil diperbarui!", "current_user": current_user, "csrf_token": csrf_token}
    )
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
    return response

@app.post("/add-user", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def add_user(
    request: Request,
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    role: Annotated[str, Form(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(require_super_admin)]
):
    # 1. Cek apakah username sudah dipakai di database
    existing_user = db.query(models.User).filter(models.User.username == username).first()
    
    if existing_user:
        # Jika username sudah ada, ambil data tabel dan kembalikan pesan error
        users = db.query(models.User).all()
        csrf_token = security.generate_csrf_token()
        response = templates.TemplateResponse(
            request=request,
            name="account.html",
            context={
                "request": request, 
                "users": users, 
                "error_msg": f"Username '{username}' sudah digunakan. Silakan gunakan nama lain!", 
                "current_user": current_user,
                "csrf_token": csrf_token
            }
        )
        response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
        return response
        
    # 2. Enkripsi kata sandi untuk pengguna baru
    hashed_password = hash_password(password)
    
    # 3. Simpan akun baru ke dalam database
    new_user = models.User(
        username=username,
        password_hash=hashed_password,
        role=role
    )
    db.add(new_user)
    db.commit()
    
    # 4. AMBIL DATA TERBARU DARI DATABASE (Ini baris penyembuh error-nya!)
    users = db.query(models.User).all()
    
    # 5. Kembalikan ke halaman dengan notifikasi sukses
    csrf_token = security.generate_csrf_token()
    response = templates.TemplateResponse(
        request=request,
        name="account.html",
        context={
            "request": request, 
            "users": users, # <--- Sekarang baris ini sudah punya nilai dari Langkah 4
            "success_msg": f"Pengguna '{username}' berhasil ditambahkan ke dalam sistem!", 
            "current_user": current_user,
            "csrf_token": csrf_token
        }
    )
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=False, samesite="strict")
    return response

# --- MENGHAPUS PENGGUNA (Hanya Super Admin) ---
@app.post("/delete-user/{user_id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def delete_user(
    user_id: int, 
    db: Annotated[Session, Depends(get_db)], 
    current_user: Annotated[models.User, Depends(require_super_admin)]
):
    user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()
    
    if user_to_delete:
        # 1. Cegah menghapus akun diri sendiri
        if user_to_delete.username == current_user.username:
            raise HTTPException(status_code=400, detail="Anda tidak bisa menghapus akun Anda sendiri!")
        
        # 2. CEGAH MENGHAPUS AKUN PATEN (Tambahkan 2 baris ini)
        if user_to_delete.username == "developer": # Sesuaikan dengan username paten Anda
            raise HTTPException(status_code=403, detail="Akses Ditolak: Ini adalah akun Paten milik Creator yang tidak boleh dihapus!")
            
        db.delete(user_to_delete)
        db.commit()
        
    return RedirectResponse(url="/account", status_code=303)


# --- EDIT ROLE PENGGUNA (Hanya Super Admin) ---
@app.post("/edit-user-role/{user_id}", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
def edit_user_role(
    user_id: int, 
    new_role: Annotated[str, Form(...)], 
    db: Annotated[Session, Depends(get_db)], 
    current_user: Annotated[models.User, Depends(require_super_admin)]
):
    user_to_edit = db.query(models.User).filter(models.User.id == user_id).first()
    
    if user_to_edit:
        # PROTEKSI MUTLAK AKUN PATEN
        if user_to_edit.username == "developer":
            raise HTTPException(status_code=403, detail="Akses Ditolak: Hak akses akun Paten tidak boleh diubah!")
            
        user_to_edit.role = new_role
        db.commit()
        
    return RedirectResponse(url="/account", status_code=303)


# --- UPLOAD / GANTI FOTO PROFIL SENDIRI ---
@app.post("/update-avatar", dependencies=[Depends(security.verify_csrf_token), Depends(audit_logger)])
async def update_avatar(
    request: Request,
    avatar_file: Annotated[UploadFile, File(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)]
):
    if avatar_file and avatar_file.filename:
        # Eksekusi Sprint 2: Batasi ekstensi dan gunakan fungsi pelindung dari CSE
        allowed_exts = ["jpg", "jpeg", "png"]
        
        # Reset file stream in case middleware/readers consumed it earlier
        await avatar_file.seek(0)
        # File akan divalidasi MIME-type nya, lalu diubah namanya menjadi UUID acak
        saved_file_path = await security.secure_save_file(avatar_file, allowed_exts, "static/avatars")
        
        current_user.profile_picture = saved_file_path
        db.commit()
        
    return RedirectResponse(url="/account", status_code=303)

# ==========================================
# SEEDER: AKUN PATEN SYSTEM CREATOR
# ==========================================
@app.on_event("startup")
def create_patent_admin():
    db = database.SessionLocal()
    try:
        developer = db.query(models.User).filter(models.User.username == "developer").first()
        if not developer:
            hashed_password = hash_password("PatenITAM2026!") 
            new_dev = models.User(
                username="developer",
                password_hash=hashed_password,
                role="Super Admin"
            )
            db.add(new_dev)
            db.commit()
        else:
            # FITUR PENYEMBUHAN (SELF-HEALING)
            # Jika akun developer terlanjur turun role, paksa kembali jadi Super Admin
            if developer.role != "Super Admin":
                developer.role = "Super Admin"
                db.commit()
    finally:
        db.close()