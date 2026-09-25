import os
import json
import types
from datetime import datetime, timedelta, timezone

import aiofiles
import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request, UploadFile, status

# Patch compatibility between modern bcrypt >= 4.0.0 and passlib 1.7.4
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = types.SimpleNamespace(__version__=bcrypt.__version__)

_orig_hashpw = bcrypt.hashpw


def _safe_hashpw(password, salt):
    if isinstance(password, str):
        password = password.encode("utf-8")
    return _orig_hashpw(password[:72], salt)


bcrypt.hashpw = _safe_hashpw

from passlib.context import CryptContext

# Kunci Rahasia Sistem — WAJIB diambil dari .env via Settings, BUKAN hardcode!
from app.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# Mesin Pengacak Password (Bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    """Mengecek apakah password ketikan user cocok dengan hash di database"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Mengacak password mentah menjadi Hash"""
    return pwd_context.hash(password)


def create_access_token(data: dict):
    """Membuat Tiket/Token KTP Digital untuk User yang berhasil Login"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# ---------------------------------------------------------
# Helper Tambahan untuk Kompatibilitas Sistem
# ---------------------------------------------------------
SECURE_COOKIES = False


def verify_jwt_token(token: str) -> dict:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token otentikasi tidak ditemukan.",
        )
    if token.startswith("Bearer "):
        token = token[7:].strip()
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


# Inisialisasi Fernet untuk Vault Kredensial — kunci diambil dari .env
VAULT_KEY = settings.VAULT_KEY.encode() if isinstance(settings.VAULT_KEY, str) else settings.VAULT_KEY
cipher_suite = Fernet(VAULT_KEY)


def encrypt_data(data: str) -> str:
    if not data:
        return ""
    return cipher_suite.encrypt(data.encode("utf-8")).decode("utf-8")


def decrypt_data(encrypted_data: str) -> str:
    if not encrypted_data:
        return ""
    try:
        return cipher_suite.decrypt(encrypted_data.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return "ERROR_DECRYPT"


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


async def secure_save_file(
    file: UploadFile, destination_path: str, max_size_mb: int = 5
):
    """
    Menyimpan file ke disk secara aman dan non-blocking (async).
    """
    allowed_extensions = {".jpg", ".jpeg", ".png", ".pdf", ".csv"}
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Ekstensi {ext} tidak diizinkan.")

    file_size = 0
    chunk_size = 1024 * 1024  # Baca per 1 MB

    try:
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
        if os.path.exists(destination_path):
            os.remove(destination_path)
        raise HTTPException(
            status_code=413,
            detail=f"Gagal: Ukuran file melebihi batas {max_size_mb} MB.",
        )

    return True


# ==========================================
# MESIN ENKRIPSI VAULT (AES-256 FERNET)
# ==========================================

# Mengambil ENCRYPTION_KEY dari Settings (.env)
ENCRYPTION_KEY = settings.ENCRYPTION_KEY if settings.ENCRYPTION_KEY else Fernet.generate_key().decode()

fernet_machine = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)


def encrypt_vault_data(plain_text: str) -> str:
    """Menggembok string menjadi teks acak"""
    if not plain_text:
        return plain_text
    return fernet_machine.encrypt(plain_text.encode()).decode()


def decrypt_vault_data(encrypted_text: str) -> str:
    """Membuka gembok teks acak menjadi string asli"""
    if not encrypted_text:
        return encrypted_text
    try:
        return fernet_machine.decrypt(encrypted_text.encode()).decode()
    except Exception:
        return "⚠️ DECRYPTION_FAILED (Kunci Salah/Data Rusak)"


# ==========================================
# MESIN ENKRIPSI DINAMIS (FERNET AES-128-CBC)
# ==========================================

# Pemuatan VAULT_SECRET_KEY dari Settings (.env)
_vault_secret = settings.VAULT_SECRET_KEY.strip("\"'") if settings.VAULT_SECRET_KEY else ""

# Fallback darurat jika lupa set .env (jangan gunakan di production!)
if not _vault_secret:
    _vault_secret = Fernet.generate_key().decode()
    print("CRITICAL WARNING: VAULT_SECRET_KEY tidak ditemukan di .env! Menggunakan kunci ephemeral (data akan hilang saat restart).")

try:
    vault_cipher = Fernet(_vault_secret.encode())
except Exception as e:
    raise ValueError(f"VAULT_SECRET_KEY tidak valid. Harus berupa 32-byte base64 encoded string. Error: {e}")

def encrypt_vault_payload(payload_dict: dict) -> str:
    """Mengubah dictionary menjadi JSON plaintext, lalu mengenkripsinya menjadi Ciphertext."""
    try:
        json_data = json.dumps(payload_dict)
        encrypted_bytes = vault_cipher.encrypt(json_data.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengenkripsi data kredensial.")

def decrypt_vault_payload(encrypted_str: str) -> dict:
    """Mendekripsi Ciphertext kembali menjadi dictionary."""
    try:
        decrypted_bytes = vault_cipher.decrypt(encrypted_str.encode('utf-8'))
        return json.loads(decrypted_bytes.decode('utf-8'))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mendekripsi data atau kunci enkripsi tidak cocok.")

# Alias untuk kompatibilitas ke fungsi lama jika ada pemanggil
encrypt_payload = encrypt_vault_payload
decrypt_payload = decrypt_vault_payload

