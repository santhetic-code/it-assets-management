import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    Kelas Settings menggunakan pydantic-settings.
    Akan otomatis membaca dari file .env di root directory.
    Jika variabel wajib (tanpa nilai default) tidak ditemukan di .env, aplikasi akan error saat startup.
    """
    # Environment Setup
    ENVIRONMENT: str = "development"

    # Database Configuration
    DATABASE_URL: str

    # Security Keys (Wajib ada di .env, tidak ada nilai fallback hardcoded!)
    SECRET_KEY: str
    VAULT_KEY: str
    
    # JWT Settings
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # Default Super Admin Initial Setup
    SUPERADMIN_USERNAME: str
    SUPERADMIN_PASSWORD: str

    # Konfigurasi Pydantic untuk melacak file .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore" # Abaikan jika ada variabel ekstra di .env yang tidak didefinisikan di sini
    )

# Inisialisasi Settings
try:
    # Memuat variabel ke dalam object 'settings'
    settings = Settings()
except ValueError as e:
    # Jika gagal membaca .env (misal SECRET_KEY tidak diisi), hentikan aplikasi
    print("❌ ERROR KRITIS: Konfigurasi .env tidak lengkap!")
    print(f"Detail Error: {e}")
    print("💡 Solusi: Pastikan file .env sudah dibuat dari .env.example dan semua nilai telah diisi.")
    raise SystemExit(1)
