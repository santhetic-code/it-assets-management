from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship, synonym

# Mengambil Base dari konfigurasi database inti kita
from app.core.database import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)

    # --- 3 KOLOM BARU UNTUK PROFIL LENGKAP ---
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    department = Column(String(50), nullable=True)

    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    avatar = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_online = Column(Boolean, default=False)

    # --- KOLOM BARU UNTUK AUDIT KEAMANAN ---
    last_login = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=get_utc_now)

    # Relasi ke log aktivitas
    audit_logs = relationship("SystemLogs", back_populates="user")

    @property
    def profile_picture(self):
        return self.avatar


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    kode_aset = Column(String(50), nullable=True, index=True)  # Opsional
    nama = Column(String(150), nullable=False)
    kelompok = Column(String(50), nullable=False)              # Monitor, Keyboard, dll
    sn_pid = Column(String(100), nullable=True, index=True)    # Opsional
    tanggal_masuk = Column(Date, nullable=True)
    tanggal_keluar = Column(Date, nullable=True)               # Bisa kosong jika belum keluar
    kepemilikan = Column(String(50), nullable=False)           # XML, MBL
    lokasi = Column(String(100), nullable=False)               # Office Blok 12, dll
    status = Column(String(50), nullable=False)                # Digunakan, Tidak Digunakan
    digunakan_oleh = Column(String(100), nullable=True)        # Nama user yang memakai

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

    # Alias / Sinonim untuk kompatibilitas dengan modul lain
    asset_tag = synonym("kode_aset")
    name = synonym("nama")
    category = synonym("kelompok")
    serial_number = synonym("sn_pid")
    assigned_to = synonym("digunakan_oleh")
    location = synonym("lokasi")


class Component(Base):
    __tablename__ = "components"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)  # Opsional, bisa tanpa relasi aset
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

    @property
    def user_pc(self):
        return self.name

    @property
    def os(self):
        return self.os_name or "-"

    @property
    def jenis_pc(self):
        if not self.pc_type:
            return "PC Operasional"
        if self.pc_type.startswith("PC "):
            return self.pc_type
        return f"PC {self.pc_type}"

    @property
    def cpu(self):
        return self.processor_spec or "-"

    @property
    def mainboard(self):
        return self.mainboard_spec or "-"

    @property
    def ram(self):
        return self.ram_spec or "-"

    @property
    def vga(self):
        return self.vga_spec or "-"

    @property
    def storage(self):
        return self.storage_spec or "-"

    @property
    def last_update(self):
        dt = self.updated_at or self.created_at
        if dt:
            months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
            return f"{dt.day} {months[dt.month - 1]} {dt.year}"
        return "11 Sep 2026"


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
    keterangan = Column(String(255), nullable=True)


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


class VaultCredential(Base):
    __tablename__ = "vault_credentials"

    id = Column(Integer, primary_key=True, index=True)
    nama_sistem = Column(String(100), nullable=False)  # Contoh: xmltronik.com
    kategori = Column(String(50), nullable=False)      # Contoh: Website, Email, Mikrotik
    kredensial_data = Column(JSON, nullable=False)     # Kolom Ajaib untuk menampung data dinamis
    akses_role = Column(String(255), default="All")    # Untuk keamanan Lapis 2 (Siapa saja yang boleh lihat)


# ==========================================
# 1. TABEL MASTER KREDENSIAL (VAULT)
# ==========================================
class Vault(Base):
    __tablename__ = "vaults"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)       # Misal: "Router Mikrotik Lobi"
    category = Column(String(50), nullable=False)    # Misal: "Network", "Database", "Server"
    url = Column(String(255), nullable=True)         # Misal: "192.168.1.1"
    username = Column(String(100), nullable=True)    # Username aset
    encrypted_password = Column(Text, nullable=False)# SANDI YANG DIGEMBOK (AES)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Penghubung ke tabel relasi
    accesses = relationship("VaultUserAccess", back_populates="vault", cascade="all, delete-orphan")
    requests = relationship("VaultRequest", back_populates="vault", cascade="all, delete-orphan")


# ==========================================
# 2. TABEL OTORISASI (ACCESS CONTROL LIST)
# ==========================================
class VaultUserAccess(Base):
    __tablename__ = "vault_user_access"

    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey("vaults.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Untuk fitur "Temporary Access" & Audit
    expires_at = Column(DateTime, nullable=True)  # Jika lewat waktu ini, akses hangus (NULL = Permanen)
    granted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Siapa yg memberi izin
    granted_at = Column(DateTime, default=datetime.utcnow)

    # Relasi
    vault = relationship("Vault", back_populates="accesses")
    user = relationship("User", foreign_keys=[user_id])
    admin = relationship("User", foreign_keys=[granted_by])


# ==========================================
# 3. TABEL REQUEST WORKFLOW (MINTA IZIN AKSES)
# ==========================================
class VaultRequest(Base):
    __tablename__ = "vault_requests"

    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey("vaults.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    reason = Column(Text, nullable=False)  # Alasan butuh akses ("Mau restart service SQL")
    status = Column(String(20), default="Pending")  # Status: Pending, Approved, Rejected

    requested_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime, nullable=True)
    responded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relasi
    vault = relationship("Vault", back_populates="requests")
    user = relationship("User", foreign_keys=[user_id])
    responder = relationship("User", foreign_keys=[responded_by])

