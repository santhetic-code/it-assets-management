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
        "Purchase", back_populates="asset", uselist=False, cascade="all, delete-orphan"
    )


class Component(Base):
    __tablename__ = "components"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    name = Column(String(100), nullable=False)
    spesifikasi = Column(Text, nullable=True)

    asset = relationship("Asset", back_populates="components")


class NetworkIP(Base):
    __tablename__ = "network_ips"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(
        String(50), unique=True, index=True, nullable=False
    )  # Harus unik
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
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False, unique=True)
    vendor = Column(String(100), nullable=True)
    purchase_date = Column(Date, nullable=True)
    cost = Column(Float, default=0.0)
    total_price = Column(
        Float, default=0.0
    )  # Nanti akan dihitung otomatis di Service layer

    asset = relationship("Asset", back_populates="purchase_info")


class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    status = Column(String(50), default="Aman")  # Aman, Perlu Dicek, Kritis
    next_schedule_date = Column(Date, nullable=True)
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
