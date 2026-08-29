from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

# Mengambil Base dari konfigurasi database inti kita
from app.core.database import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="Auditor")  # Super Admin, Staff IT, Auditor
    avatar = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

    # Relasi ke log aktivitas
    audit_logs = relationship("SystemLogs", back_populates="user")

    @property
    def profile_picture(self):
        return self.avatar


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_tag = Column(
        String(50), unique=True, index=True, nullable=False
    )  # Harus unik
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="Digunakan")
    assigned_to = Column(String(100), nullable=True)
    location = Column(String(100), nullable=True)
    serial_number = Column(String(100), nullable=True)
    condition = Column(String(50), default="Baru")
    usage_status = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    # Relasi ke tabel lain (Satu Aset bisa punya banyak Komponen, Log, dll)
    components = relationship(
        "Component", back_populates="asset", cascade="all, delete-orphan"
    )
    maintenance_logs = relationship(
        "MaintenanceLog", back_populates="asset", cascade="all, delete-orphan"
    )
    health_reports = relationship(
        "HealthMonitoring", back_populates="asset", cascade="all, delete-orphan"
    )
    purchase_info = relationship(
        "Purchase", back_populates="asset", cascade="all, delete-orphan"
    )


class Component(Base):
    __tablename__ = "components"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)  # Wajib ada untuk relasi
    name = Column(String(100), nullable=False)  # Misalnya: "PC - DIREKTUR"

    # Kolom baru hasil adaptasi dari Spreadsheet
    os_name = Column(String(255), nullable=True)
    ram_spec = Column(String(255), nullable=True)
    vga_spec = Column(String(255), nullable=True)  # Mewakili VGA / GPU Card
    processor_spec = Column(String(255), nullable=True)  # Mewakili CPU / Processor
    mainboard_spec = Column(String(255), nullable=True)
    storage_spec = Column(String(500), nullable=True)  # Mewakili HDD/SSD
    monitor = Column(String(255), nullable=True)
    keyboard = Column(String(255), nullable=True)
    mouse = Column(String(255), nullable=True)
    pc_type = Column(String(50), nullable=True, default="Operasional")  # Operasional / Server
    psu = Column(String(255), nullable=True)
    casing = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    # Relationship back to Asset
    asset = relationship("Asset", back_populates="components")


class NetworkIP(Base):
    __tablename__ = "network_ips"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(
        String(50), unique=True, index=True, nullable=False
    )  # Harus unik
    ip_type = Column(String(50), default="Operasional")
    assigned_to = Column(String(100), nullable=True)
    mac_address = Column(String(50), nullable=True)
    description = Column(String(255), nullable=True)
    status = Column(String(50), default="Aktif")


class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    url = Column(String(255), nullable=True)
    username = Column(String(100), nullable=False)
    password_hash = Column(
        Text, nullable=False
    )  # Disimpan dalam bentuk enkripsi Fernet
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(
        Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    item_name = Column(String(150), nullable=True)
    vendor = Column(String(100), nullable=True)
    purchase_date = Column(Date, nullable=True)
    price_per_item = Column(Float, default=0.0)
    quantity = Column(Integer, default=1)
    cost = Column(Float, default=0.0)
    total_price = Column(Float, default=0.0)
    buyer_name = Column(String(100), nullable=True)
    invoice_link = Column(String(255), nullable=True)
    nota_file = Column(String(255), nullable=True)

    asset = relationship("Asset", back_populates="purchase_info")


class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(
        Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    task_type = Column(String(100), nullable=True)
    location_target = Column(String(100), nullable=True)
    last_maintenance_date = Column(Date, nullable=True)
    next_schedule_date = Column(Date, nullable=True)
    interval_months = Column(Integer, default=3)
    status = Column(String(50), default="Aman")  # Aman, Perlu Dicek, Kritis
    notes = Column(Text, nullable=True)

    asset = relationship("Asset", back_populates="maintenance_logs")


class HealthMonitoring(Base):
    __tablename__ = "health_monitoring"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    disk_c_free_gb = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)
    ram_usage_percent = Column(Float, nullable=True)
    checked_at = Column(DateTime, default=get_utc_now)

    asset = relationship("Asset", back_populates="health_reports")


class SystemLogs(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(
        String(255), nullable=False
    )  # Cth: "Mengubah Aset", "Reveal Password"
    entity = Column(String(50), nullable=True)  # Cth: "Asset", "Credential"
    entity_id = Column(Integer, nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=get_utc_now)

    user = relationship("User", back_populates="audit_logs")
