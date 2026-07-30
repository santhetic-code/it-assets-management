from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Kelas Settings menggunakan pydantic-settings.
    Akan otomatis membaca dari file .env di root directory.
    """

    # Environment Setup
    ENVIRONMENT: str = "development"

    # Database Configuration
    DATABASE_URL: str

    # Security Keys
    SECRET_KEY: str
    VAULT_KEY: str

    # JWT Settings
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # Default Super Admin Initial Setup
    SUPERADMIN_USERNAME: str
    SUPERADMIN_PASSWORD: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


try:
    settings = Settings()
except ValueError as e:
    print("❌ ERROR KRITIS: Konfigurasi .env tidak lengkap!")
    print(f"Detail Error: {e}")
    raise SystemExit(1)
