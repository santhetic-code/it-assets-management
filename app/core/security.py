import os
from datetime import datetime, timedelta, timezone

import aiofiles
import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request, UploadFile, status

# Import konfigurasi yang aman dari config.py
from app.core.config import settings

# ---------------------------------------------------------
# 1. SETUP KEAMANAN & KRIPTOGRAFI
# ---------------------------------------------------------
SECRET_KEY = settings.SECRET_KEY
VAULT_KEY = settings.VAULT_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# Otomatis True jika ENVIRONMENT="production", False jika "development"
SECURE_COOKIES = settings.ENVIRONMENT.lower() == "production"

# Inisialisasi Fernet untuk Vault Kredensial
cipher_suite = Fernet(VAULT_KEY.encode() if isinstance(VAULT_KEY, str) else VAULT_KEY)


# ---------------------------------------------------------
# 2. HASHING PASSWORD & JWT TOKEN
# ---------------------------------------------------------
def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_jwt_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi login telah kedaluwarsa.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token otentikasi tidak valid.",
        )


# ---------------------------------------------------------
# 3. ENKRIPSI BRANKAS KREDENSIAL (VAULT)
# ---------------------------------------------------------
def encrypt_data(data: str) -> str:
    if not data:
        return ""
    return cipher_suite.encrypt(data.encode("utf-8")).decode("utf-8")


def decrypt_data(encrypted_data: str) -> str:
    if not encrypted_data:
        return ""
    try:
        return cipher_suite.decrypt(encrypted_data.encode("utf-8")).decode("utf-8")
    except InvalidToken:  # Fix: Tidak lagi menangkap blind Exception
        return "ERROR_DECRYPT"


# ---------------------------------------------------------
# 4. DEPENDENCY CSRF (Cross-Site Request Forgery)
# ---------------------------------------------------------
async def verify_csrf_token(request: Request):
    """
    Memverifikasi token CSRF. Akan diwajibkan di semua route POST/PUT/DELETE.
    """
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return True

    cookie_csrf = request.cookies.get("csrf_token")
    header_csrf = request.headers.get("X-CSRF-Token")

    form_csrf = None
    if request.headers.get(
        "content-type"
    ) == "application/x-www-form-urlencoded" or request.headers.get(
        "content-type", ""
    ).startswith("multipart/form-data"):
        form = await request.form()
        form_csrf = form.get("csrf_token")

    client_csrf = header_csrf or form_csrf

    if not cookie_csrf or not client_csrf or cookie_csrf != client_csrf:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Akses Ditolak: Potensi CSRF!"
        )
    return True


# ---------------------------------------------------------
# 5. UPLOAD FILE AMAN (Asynchronous I/O)
# ---------------------------------------------------------
async def secure_save_file(
    file: UploadFile, destination_path: str, max_size_mb: int = 5
):
    """
    Menyimpan file ke disk secara aman dan non-blocking (async).
    Memvalidasi ekstensi dan membatasi ukuran.
    """
    allowed_extensions = {".jpg", ".jpeg", ".png", ".pdf", ".csv"}
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Ekstensi {ext} tidak diizinkan.")

    file_size = 0
    chunk_size = 1024 * 1024  # Baca per 1 MB

    try:
        # Fix: Menggunakan aiofiles.open alih-alih open() biasa
        async with aiofiles.open(destination_path, "wb") as buffer:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                file_size += len(chunk)

                if file_size > (max_size_mb * 1024 * 1024):
                    raise ValueError("FILE_TOO_LARGE")

                await buffer.write(chunk)
    except ValueError:
        # Jika ukurannya melebihi batas, hapus file sebagian yang terlanjur ditulis
        if os.path.exists(destination_path):
            os.remove(destination_path)
        raise HTTPException(
            status_code=413,
            detail=f"Gagal: Ukuran file melebihi batas {max_size_mb} MB.",
        )

    return True
