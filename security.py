import os
import uuid
import jwt
import secrets
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, UploadFile

load_dotenv()

# Gunakan kunci dari .env, atau gunakan kunci bawaan jika di localhost
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_rahasia_jika_env_tidak_terbaca")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_jwt_token(token: str):
    if not token:
        raise HTTPException(status_code=401, detail="Sesi tidak ditemukan.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Token tidak valid.")
        return username
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise HTTPException(status_code=401, detail="Sesi tidak valid atau kedaluwarsa.")

def generate_csrf_token():
    return secrets.token_urlsafe(32)

async def verify_csrf_token(request: Request):
    csrf_cookie = request.cookies.get("csrf_token")
    
    # Adaptasi SE: Jika request berupa JSON (dari Fetch API), baca token dari Header
    if request.headers.get("content-type") == "application/json":
        csrf_client = request.headers.get("X-CSRF-Token")
    else:
        form_data = await request.form()
        csrf_client = form_data.get("csrf_token")
        
    if not csrf_cookie or not csrf_client or csrf_cookie != csrf_client:
        raise HTTPException(status_code=403, detail="Akses Ditolak: Potensi CSRF!")


# ==========================================
# 3. MIDDLEWARE: PROTEKSI UPLOAD FILE (SPRINT 2)
# ==========================================
MAGIC_NUMBERS = {
    "png": b'\x89PNG\r\n\x1a\n',
    "jpg": b'\xff\xd8\xff',
    "jpeg": b'\xff\xd8\xff',
    "pdf": b'%PDF-',
}

async def secure_save_file(upload_file: UploadFile, allowed_extensions: list, destination_folder: str) -> str:
    ext = upload_file.filename.split('.')[-1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Tipe file .{ext} tidak diizinkan untuk diunggah.")
    
    header_bytes = await upload_file.read(10)
    await upload_file.seek(0)
    
    is_valid_magic = False
    for allowed_ext in allowed_extensions:
        if allowed_ext in MAGIC_NUMBERS and header_bytes.startswith(MAGIC_NUMBERS[allowed_ext]):
            is_valid_magic = True
            break
            
    if not is_valid_magic:
        raise HTTPException(status_code=400, detail="Integritas file diragukan (Potensi Spoofing Ekstensi Terdeteksi!).")

    safe_filename = f"{uuid.uuid4().hex}.{ext}"
    os.makedirs(destination_folder, exist_ok=True)
    file_path = os.path.join(destination_folder, safe_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(await upload_file.read())
        
    return f"/{file_path}"

# ==========================================
# 4. MIDDLEWARE: SANITASI CSV / IMPORT MASSAL (SPRINT 3)
# ==========================================
def sanitize_csv_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    dangerous_chars = ('=', '+', '-', '@', '\t', '\r')
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(
                lambda x: f"'{x}" if isinstance(x, str) and x.startswith(dangerous_chars) else x
            )
    return df