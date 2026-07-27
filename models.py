from sqlalchemy import Column, Integer, String, ForeignKey, Date, Text, Float, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_tag = Column(String(50), unique=True, index=True) # Kode Aset (Cth: MON-1, PC-HRD)
    name = Column(String(100))
    category = Column(String(50)) # Kelompok (Monitor, PC, Server, dll)
    serial_number = Column(String(100), nullable=True) # SN/PID
    ownership = Column(String(50), nullable=True) # Kepemilikan (XML, dll)
    location = Column(String(100)) # Lokasi (Kantor Utama, Blok 12)
    
    # Status & Kondisi
    condition = Column(String(50), default="Baru") # Baru, Bekas, Rusak
    usage_status = Column(String(50), default="Digunakan") # Digunakan, Tidak Digunakan, Tidak Layak
    assigned_to = Column(String(100), nullable=True) # Digunakan Oleh (Divisi/User)
    notes = Column(Text, nullable=True) # Keterangan Tambahan
    
    # Relasi
    components = relationship("Component", back_populates="asset")
    network_ips = relationship("NetworkIP", back_populates="asset")
    health_reports = relationship("HealthMonitoring", back_populates="asset")
    maintenance_logs = relationship("MaintenanceLog", back_populates="asset")

class Component(Base):
    __tablename__ = "components"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True) # Relasi ke Aset
    assigned_to = Column(String(100), nullable=True) # User/assigned person (String)
    os_name = Column(String(100), nullable=True)
    processor_spec = Column(String(150), nullable=True)
    mainboard_spec = Column(String(150), nullable=True)
    ram_spec = Column(String(150), nullable=True)
    vga_spec = Column(String(150), nullable=True)
    storage_spec = Column(String(150), nullable=True)
    pc_category = Column(String(50), nullable=True) # Server / Operasional
    location = Column(String(100), nullable=True) # Lokasi PC

    asset = relationship("Asset", back_populates="components")

class NetworkIP(Base):
    __tablename__ = "network_ips"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(50), unique=True, index=True)
    subnet_mask = Column(String(50), default="255.255.255.0")
    status = Column(String(50), default="Available")
    assigned_to_asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    ip_type = Column(String(50), nullable=True) # Server / Operasional
    assigned_to = Column(String(100), nullable=True) # Di gunakan oleh (String)

    asset = relationship("Asset", back_populates="network_ips")

class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True)
    service_type = Column(String(50)) # Web Login, Radmin, VPN, Database, CCTV
    title = Column(String(100)) # Nama Layanan/Rincian
    access_url_or_ip = Column(String(100), nullable=True) # Acces (IP / Link)
    username = Column(String(100))
    password_hash = Column(String(255)) # Disimpan sebagai hash/enkripsi
    division = Column(String(100), nullable=True) # Divisi (Accounting, Opr & CS, dll)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)

class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    purchase_date = Column(Date, default=datetime.date.today)
    item_name = Column(String(150))
    vendor = Column(String(100)) # Nama Toko
    price_per_item = Column(Float)
    quantity = Column(Integer, default=1)
    total_price = Column(Float)
    buyer_name = Column(String(100)) # Dibeli Oleh
    invoice_link = Column(String(255), nullable=True) # Link Marketplace

class HealthMonitoring(Base):
    __tablename__ = "health_monitoring"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"))
    check_date = Column(Date, default=datetime.date.today)
    
    # Resource Usage
    cpu_usage_percent = Column(Float, nullable=True)
    memory_usage_percent = Column(Float, nullable=True)
    
    # Storage Health & Free Space (Disimulasikan untuk C dan D)
    disk_c_health = Column(String(50), nullable=True) # GOOD 98%, CAUTION 1%
    disk_c_free_gb = Column(Float, nullable=True)
    disk_d_health = Column(String(50), nullable=True)
    disk_d_free_gb = Column(Float, nullable=True)
    
    status_alert = Column(String(50)) # Aman, Warning, Perhatian

    asset = relationship("Asset", back_populates="health_reports")

class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    location_target = Column(String(100), nullable=True) # Untuk AC (Cth: Kantor Blok 14)
    task_type = Column(String(100)) # Cth: Cuci AC, Update OS
    
    last_maintenance_date = Column(Date)
    interval_months = Column(Integer, default=3) # Interval (Bulan)
    next_schedule_date = Column(Date) # Jadwal Berikutnya
    status = Column(String(50), default="Aman") # Aman, Jatuh Tempo

    asset = relationship("Asset", back_populates="maintenance_logs")

# Tambahkan ini di bagian paling bawah models.py
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Tambahkan angka batasan panjang karakter di dalam String()
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(255))
    role = Column(String(50), default="Staff IT")
    profile_picture = Column(String(255), nullable=True)


class SystemLogs(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), index=True)       # Mencatat username dari token JWT
    action = Column(String(100))                   # Mencatat metode: POST, PUT, DELETE
    endpoint = Column(String(100))                 # Mencatat rute yang dieksekusi (contoh: /assets/)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow) # Waktu presisi saat aksi dilakukan
    ip_address = Column(String(50), nullable=True) # Mencatat IP asal dari perangkat pengguna