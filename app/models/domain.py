from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text
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

    @property
    def nama_lengkap(self):
        return self.full_name

    @property
    def avatar_url(self):
        if not self.avatar:
            return "/static/avatars/default.png"
        if self.avatar.startswith("/") or self.avatar.startswith("http"):
            return self.avatar
        return f"/static/avatars/{self.avatar}"


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

    # Soft Delete Columns
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

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


# ==========================================
# MASTER DATA KOMPONEN (Dropdown Reference)
# ==========================================
class MasterComponent(Base):
    __tablename__ = "master_components"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), index=True)         # CPU, RAM, OS, VGA, Storage, Monitor
    name = Column(String(150), unique=True, index=True) # Cth: 'Intel Core i7-13700F'
    description = Column(String(255), nullable=True)


class Component(Base):
    __tablename__ = "components"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    name = Column(String(100), nullable=False)

    # --- KOLOM STRING REDUNDAN TELAH DIBUANG ---
    # os_name, ram_spec, vga_spec, processor_spec, mainboard_spec, storage_spec, monitor DIHAPUS.

    # Periferal yang belum di-master-kan (Bisa di-upgrade ke tabel terpisah nanti)
    keyboard = Column(String(255), nullable=True)
    mouse = Column(String(255), nullable=True)
    pc_type = Column(String(50), nullable=True, default="Operasional")
    psu = Column(String(255), nullable=True)
    casing = Column(String(255), nullable=True)

    # --- FOREIGN KEY WAJIB (Single Source of Truth) ---
    os_id = Column(Integer, ForeignKey("master_components.id"), nullable=True)
    cpu_id = Column(Integer, ForeignKey("master_components.id"), nullable=True)
    mainboard_id = Column(Integer, ForeignKey("master_components.id"), nullable=True)
    ram_id = Column(Integer, ForeignKey("master_components.id"), nullable=True)
    vga_id = Column(Integer, ForeignKey("master_components.id"), nullable=True)
    storage_id = Column(Integer, ForeignKey("master_components.id"), nullable=True)
    monitor_id = Column(Integer, ForeignKey("master_components.id"), nullable=True)

    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    # Soft Delete Columns
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    asset = relationship("Asset", back_populates="components")
    history = relationship("ComponentHistory", back_populates="component", cascade="all, delete-orphan")

    # Master Component Relationships
    os_ref       = relationship("MasterComponent", foreign_keys=[os_id])
    cpu_ref      = relationship("MasterComponent", foreign_keys=[cpu_id])
    mainboard_ref= relationship("MasterComponent", foreign_keys=[mainboard_id])
    ram_ref      = relationship("MasterComponent", foreign_keys=[ram_id])
    vga_ref      = relationship("MasterComponent", foreign_keys=[vga_id])
    storage_ref  = relationship("MasterComponent", foreign_keys=[storage_id])
    monitor_ref  = relationship("MasterComponent", foreign_keys=[monitor_id])

    # --- PROPERTY DIBERSIHKAN: Hanya membaca dari relasi master ---
    @property
    def identitas_pc(self):
        return self.name

    @property
    def jenis_pc(self):
        if not self.pc_type:
            return "PC Operasional"
        return self.pc_type if self.pc_type.startswith("PC ") else f"PC {self.pc_type}"

    @property
    def os(self):
        return self.os_ref.name if self.os_ref else "-"

    @property
    def cpu(self):
        return self.cpu_ref.name if self.cpu_ref else "-"

    @property
    def mainboard(self):
        return self.mainboard_ref.name if self.mainboard_ref else "-"

    @property
    def ram(self):
        return self.ram_ref.name if self.ram_ref else "-"

    @property
    def vga(self):
        return self.vga_ref.name if self.vga_ref else "-"

    @property
    def storage(self):
        return self.storage_ref.name if self.storage_ref else "-"

    @property
    def monitor_display(self):
        return self.monitor_ref.name if self.monitor_ref else "-"

    @property
    def last_update(self):
        dt = self.updated_at or self.created_at
        if dt:
            months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
            return f"{dt.day} {months[dt.month - 1]} {dt.year}"
        return "-"


# ==========================================
# RIWAYAT PERUBAHAN KOMPONEN (Audit Trail)
# ==========================================
class ComponentHistory(Base):
    __tablename__ = "component_history"

    id = Column(Integer, primary_key=True, index=True)
    component_id = Column(Integer, ForeignKey("components.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action_type = Column(String(50), nullable=False)  
    
    # UBAH DARI Text MENJADI JSON
    changes_detail = Column(JSON, nullable=False)     
    
    created_at = Column(DateTime, default=get_utc_now)

    component = relationship("Component", back_populates="history")
    user = relationship("User", foreign_keys=[user_id])


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
    
    # UBAH DARI String(255) MENJADI JSON
    action = Column(JSON, nullable=False)  
    
    entity = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=get_utc_now)

    user = relationship("User", back_populates="audit_logs")




# ==========================================
# 1. TABEL MASTER KREDENSIAL (VAULT)
# ==========================================
class Vault(Base):
    __tablename__ = "vaults"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    url = Column(String(255), nullable=True)
    
    # Kolom ini akan menampung SELURUH data dinamis (username, password, PIN, API Key, dll)
    encrypted_payload = Column(Text, nullable=False) 
    
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relasi yang sudah kita buat sebelumnya tetap dibiarkan
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


# ==========================================
# PURCHASE / PENGADAAN BARANG
# ==========================================
class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)

    # Opsional: link ke aset tertentu (jika pembelian adalah penggantian/upgrade aset)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)

    item_name = Column(String(255), nullable=False)
    vendor = Column(String(255), nullable=True)

    # DECIMAL presisi tinggi untuk data keuangan (15 digit, 2 angka di belakang koma)
    unit_price = Column(Numeric(15, 2), nullable=False, default=0)
    quantity = Column(Integer, nullable=False, default=1)
    total_price = Column(Numeric(15, 2), nullable=False, default=0)

    purchase_date = Column(Date, nullable=False)
    category = Column(String(100), nullable=True)       # Perangkat Keras, Lisensi, dll.
    description = Column(Text, nullable=True)

    # Lokasi file nota/invoice yang di-upload (relatif ke static/)
    file_path = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=get_utc_now)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Soft Delete Columns
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relasi
    asset = relationship("Asset", back_populates="purchase_info", foreign_keys=[asset_id])
    creator = relationship("User", foreign_keys=[created_by])
