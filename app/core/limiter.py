from slowapi import Limiter
from slowapi.util import get_remote_address

# Inisialisasi pembatasan berdasarkan IP Address (remote address) pengguna
limiter = Limiter(key_func=get_remote_address)
