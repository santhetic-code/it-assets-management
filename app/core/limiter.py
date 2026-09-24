import os
from slowapi import Limiter
from slowapi.util import get_remote_address

# Ambil dari Environment Variable, fallback ke 'redis' (nama service di docker-compose)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Inisialisasi Limiter dengan Redis Storage
# Ini menjamin Rate Limit berjalan tersentralisasi dan mendukung multi-worker Uvicorn
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=REDIS_URL
)
