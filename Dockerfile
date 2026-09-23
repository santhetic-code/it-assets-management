# Menggunakan image Python versi ringan (slim)
FROM python:3.10-slim

# Mencegah Python menulis file .pyc ke disk
ENV PYTHONDONTWRITEBYTECODE=1
# Mencegah Python mem-buffer stdout dan stderr
ENV PYTHONUNBUFFERED=1

# Menentukan direktori kerja di dalam container
WORKDIR /app

# Menginstal dependensi sistem yang mungkin dibutuhkan oleh library Python (seperti mysqlclient)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Menyalin file requirements terlebih dahulu (untuk memanfaatkan cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Menyalin seluruh kode aplikasi ke dalam container
COPY . .

# Mengekspos port internal container
EXPOSE 8000

# Perintah untuk menjalankan aplikasi
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
