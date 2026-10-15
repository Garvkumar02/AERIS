import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    LargeBinary,
    JSON,
    Text
)
from sqlalchemy.orm import relationship
from .database import Base

def gen_uuid_str():
    return str(uuid.uuid4())

class Campus(Base):
    __tablename__ = "campuses"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_m = Column(Integer, nullable=False, default=300)
    wifi_bssids = Column(JSON, default=list)  # Stored as JSON list of strings
    timezone = Column(String(50), nullable=False, default="Asia/Kolkata")

    users = relationship("User", back_populates="campus")
    attendances = relationship("Attendance", back_populates="campus")
    buildings = relationship("Building", back_populates="campus", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    employee_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="student")  # 'student' | 'faculty' | 'staff' | 'guard' | 'worker' | 'visitor' | 'admin'
    department = Column(String(100), nullable=True, default="CSE")
    designation = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    status = Column(String(50), nullable=False, default="active")  # 'active' | 'suspended' | 'revoked'
    campus_id = Column(String(36), ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True)
    mentor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    campus = relationship("Campus", back_populates="users")
    biometric_profile = relationship("BiometricProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="user", cascade="all, delete-orphan")
    attempts = relationship("VerificationAttempt", back_populates="user", cascade="all, delete-orphan")
    teaching_sessions = relationship("TimetableSession", back_populates="faculty")
    work_shifts = relationship("WorkShift", back_populates="user")
    visitor_passes = relationship("VisitorPass", foreign_keys="VisitorPass.visitor_id", back_populates="visitor")
    gate_events = relationship("GateEvent", foreign_keys="GateEvent.user_id", back_populates="user", cascade="all, delete-orphan")
    taught_lectures = relationship("LectureSession", back_populates="faculty")
    room_presences = relationship("RoomPresence", back_populates="user", cascade="all, delete-orphan")
    mentor = relationship("User", remote_side=[id], foreign_keys=[mentor_id], backref="mentees")
    notifications = relationship("Notification", foreign_keys="Notification.recipient_id", back_populates="recipient", cascade="all, delete-orphan")
    mentor_alerts_received = relationship("MentorAlert", foreign_keys="MentorAlert.mentor_id", back_populates="mentor", cascade="all, delete-orphan")
    mentor_alerts_for_student = relationship("MentorAlert", foreign_keys="MentorAlert.student_id", back_populates="student", cascade="all, delete-orphan")
    biometric_access_logs_made = relationship("BiometricAccessLog", foreign_keys="BiometricAccessLog.accessor_id", back_populates="accessor", cascade="all, delete-orphan")
    biometric_access_logs_target = relationship("BiometricAccessLog", foreign_keys="BiometricAccessLog.target_user_id", back_populates="target_user", cascade="all, delete-orphan")

class BiometricProfile(Base):
    __tablename__ = "biometric_profiles"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    encrypted_embedding = Column(LargeBinary, nullable=False)
    model_version = Column(String(50), nullable=False, default="buffalo_l")
    consent_version = Column(String(50), nullable=False, default="1.0")
    purpose_limitation = Column(String(100), default="CAMPUS_IDENTITY_AND_ATTENDANCE_ONLY", nullable=False)
    storage_classification = Column(String(50), default="RESTRICTED_SPECIAL_CATEGORY_PVI", nullable=False)
    encryption_algorithm = Column(String(50), default="AES-256-GCM/FERNET", nullable=False)
    consent_status = Column(String(50), default="CONSENT_GRANTED", nullable=False)  # CONSENT_GRANTED, CONSENT_REVOKED, DATA_ERASED
    consent_timestamp = Column(DateTime, default=datetime.utcnow)
    revoked_timestamp = Column(DateTime, nullable=True)
    deletion_receipt_hash = Column(String(64), nullable=True)
    raw_image_persisted = Column(Boolean, default=False, nullable=False)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="biometric_profile")

class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(String(255), nullable=False)
    platform = Column(String(50), default="android")
    status = Column(String(50), default="active")
    last_seen = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="devices")

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    campus_id = Column(String(36), ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True)
    day = Column(Date, nullable=False, index=True)
    checked_in_at = Column(DateTime, default=datetime.utcnow)
    lecture_session_id = Column(String(36), ForeignKey("lecture_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    verification_method = Column(String(50), default="DOUBLE_VERIFICATION", nullable=False)
    face_score = Column(Float, nullable=True)
    distance_m = Column(Float, nullable=True)
    os_biometric_verified = Column(Boolean, default=False)
    risk_score = Column(Integer, nullable=True)
    device_id = Column(String(255), nullable=True)
    prev_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=True, index=True)

    user = relationship("User", back_populates="attendances")
    campus = relationship("Campus", back_populates="attendances")
    lecture_session = relationship("LectureSession", back_populates="attendances")

class VerificationAttempt(Base):
    __tablename__ = "verification_attempts"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    result = Column(String(50), nullable=False)  # ACCEPT | REJECT
    failure_code = Column(String(100), nullable=True)
    face_score = Column(Float, nullable=True)
    yaw_delta = Column(Float, nullable=True)
    distance_m = Column(Float, nullable=True)
    gps_accuracy = Column(Float, nullable=True)
    is_mock = Column(Boolean, nullable=True)
    device_id = Column(String(255), nullable=True)
    risk_score = Column(Integer, nullable=True)

    user = relationship("User", back_populates="attempts")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(String(36), nullable=True)
    action = Column(String(100), nullable=False)
    entity = Column(String(100), nullable=True)
    entity_id = Column(String(100), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    prev_hash = Column(String(64), nullable=True)
    record_hash = Column(String(64), nullable=True, index=True)

# ========================================================
# Phase 2 Infrastructure & Spatial Registry Models
# ========================================================

class Building(Base):
    __tablename__ = "buildings"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    campus_id = Column(String(36), ForeignKey("campuses.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    campus = relationship("Campus", back_populates="buildings")
    floors = relationship("Floor", back_populates="building", cascade="all, delete-orphan")

class Floor(Base):
    __tablename__ = "floors"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    building_id = Column(String(36), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False)
    floor_number = Column(Integer, nullable=False, default=0)
    name = Column(String(100), nullable=False)

    building = relationship("Building", back_populates="floors")
    rooms = relationship("Room", back_populates="floor", cascade="all, delete-orphan")

class Room(Base):
    __tablename__ = "rooms"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    floor_id = Column(String(36), ForeignKey("floors.id", ondelete="CASCADE"), nullable=False)
    room_number = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    room_type = Column(String(50), nullable=False, default="lecture_hall")  # lecture_hall, lab, auditorium, library, office, gate
    capacity = Column(Integer, nullable=False, default=60)
    current_occupancy = Column(Integer, default=0)
    authorized_roles = Column(JSON, default=list)  # ["all"] or ["faculty", "staff", "admin"]
    indoor_beacon_uuid = Column(String(100), nullable=True)
    wifi_bssid = Column(String(50), nullable=True)
    qr_secret = Column(String(64), nullable=True)

    floor = relationship("Floor", back_populates="rooms")
    sessions = relationship("TimetableSession", back_populates="room", cascade="all, delete-orphan")
    lecture_sessions = relationship("LectureSession", back_populates="room", cascade="all, delete-orphan")
    presences = relationship("RoomPresence", back_populates="room", cascade="all, delete-orphan")

class TimetableSession(Base):
    __tablename__ = "timetable_sessions"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    faculty_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_name = Column(String(150), nullable=False)
    subject_code = Column(String(50), nullable=False)
    day_of_week = Column(String(10), nullable=False)  # Mon, Tue, Wed, Thu, Fri, Sat
    start_time = Column(String(10), nullable=False)  # HH:MM
    end_time = Column(String(10), nullable=False)  # HH:MM
    department = Column(String(100), nullable=False, default="CSE")
    section = Column(String(50), nullable=False, default="Section A")

    room = relationship("Room", back_populates="sessions")
    faculty = relationship("User", back_populates="teaching_sessions")

class WorkShift(Base):
    __tablename__ = "work_shifts"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    shift_name = Column(String(100), nullable=False)
    start_time = Column(String(10), nullable=False)  # HH:MM
    end_time = Column(String(10), nullable=False)  # HH:MM
    assigned_location = Column(String(100), nullable=False)
    days = Column(String(100), nullable=False, default="Mon,Tue,Wed,Thu,Fri")

    user = relationship("User", back_populates="work_shifts")

class VisitorPass(Base):
    __tablename__ = "visitor_passes"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    visitor_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    host_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    purpose = Column(String(255), nullable=False)
    badge_number = Column(String(50), nullable=False)
    valid_from = Column(DateTime, nullable=False, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False, default="active")  # active, expired, checked_out

    visitor = relationship("User", foreign_keys=[visitor_id], back_populates="visitor_passes")
    host = relationship("User", foreign_keys=[host_user_id])

class GateDevice(Base):
    __tablename__ = "gate_devices"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    device_id = Column(String(100), unique=True, nullable=False, index=True)
    gate_id = Column(String(50), nullable=False, index=True)  # e.g. GATE-MAIN-01
    gate_name = Column(String(150), nullable=False)
    location = Column(String(150), nullable=True, default="Main Campus Entry")
    status = Column(String(50), nullable=False, default="authorized")  # authorized, revoked, maintenance
    api_key_hash = Column(String(64), nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_heartbeat = Column(DateTime, nullable=True)

class GateEvent(Base):
    __tablename__ = "gate_events"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    gate_id = Column(String(50), nullable=False, index=True)  # e.g. GATE-01
    direction = Column(String(10), nullable=False)  # ENTRY or EXIT
    event_type = Column(String(50), nullable=False)  # DYNAMIC_QR, GUARD_OVERRIDE, VISITOR_PASS, OFFLINE_SYNC, BIOMETRIC
    guard_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    override_reason = Column(String(255), nullable=True)
    device_id = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    client_event_id = Column(String(64), unique=True, nullable=True, index=True)
    synced_offline = Column(Boolean, default=False, nullable=False)
    offline_device_timestamp = Column(DateTime, nullable=True)
    prev_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=False)

    user = relationship("User", foreign_keys=[user_id], back_populates="gate_events")
    guard = relationship("User", foreign_keys=[guard_id])

class LectureSession(Base):
    __tablename__ = "lecture_sessions"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    timetable_session_id = Column(String(36), ForeignKey("timetable_sessions.id", ondelete="SET NULL"), nullable=True)
    faculty_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_name = Column(String(150), nullable=False)
    subject_code = Column(String(50), nullable=False)
    section = Column(String(50), nullable=False, default="Section A")
    status = Column(String(20), nullable=False, default="active")  # 'active' | 'ended'
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    secret_key = Column(String(64), nullable=False)  # 32-byte hex HMAC secret

    faculty = relationship("User", back_populates="taught_lectures")
    room = relationship("Room", back_populates="lecture_sessions")
    timetable_session = relationship("TimetableSession")
    attendances = relationship("Attendance", back_populates="lecture_session", cascade="all, delete-orphan")

class RoomPresence(Base):
    __tablename__ = "room_presences"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    check_in_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    check_out_at = Column(DateTime, nullable=True)
    verification_method = Column(String(50), nullable=False)  # INDOOR_QR, BLE_BEACON, WIFI_BSSID, RFID_NFC, FACIAL_KIOSK, MANUAL_OVERRIDE
    device_id = Column(String(255), nullable=True)
    evidence_payload = Column(JSON, nullable=True)
    status = Column(String(20), default="active", nullable=False)  # active, completed, expired
    prev_hash = Column(String(64), nullable=True)
    presence_hash = Column(String(64), nullable=False, index=True)

    user = relationship("User", back_populates="room_presences")
    room = relationship("Room", back_populates="presences")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    recipient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # ATTENDANCE_SUCCESS, ATTENDANCE_FAILURE, CLASS_RESCHEDULED, ROOM_CHANGED, EXAM_ALERT, MENTOR_ABSENCE_ALERT, SYSTEM_ADVISORY
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    priority = Column(String(20), default="NORMAL", nullable=False)  # LOW, NORMAL, HIGH, URGENT
    channel = Column(String(30), default="IN_APP", nullable=False)  # IN_APP, PUSH, SMS, EMAIL
    delivery_status = Column(String(30), default="PENDING", index=True, nullable=False)  # PENDING, SENT, DELIVERED, FAILED, SUPPRESSED_DUPLICATE
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    last_attempt_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    dedup_key = Column(String(128), nullable=True, index=True)
    metadata_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="notifications")
    mentor_alert = relationship("MentorAlert", back_populates="notification", uselist=False)

class MentorAlert(Base):
    __tablename__ = "mentor_alerts"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    student_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mentor_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lecture_session_id = Column(String(36), ForeignKey("lecture_sessions.id", ondelete="SET NULL"), nullable=True)
    timetable_session_id = Column(String(36), ForeignKey("timetable_sessions.id", ondelete="SET NULL"), nullable=True)
    subject_name = Column(String(150), nullable=False)
    subject_code = Column(String(50), nullable=False)
    room_number = Column(String(50), nullable=True)
    absence_duration_minutes = Column(Integer, nullable=False, default=10)
    gate_presence_status = Column(String(50), default="UNKNOWN")  # ON_CAMPUS_GATE_VERIFIED, OFF_CAMPUS, UNKNOWN
    room_presence_status = Column(String(50), default="NOT_IN_ASSIGNED_ROOM")
    status = Column(String(50), default="ADVISORY_PENDING", nullable=False)  # ADVISORY_PENDING, STUDENT_CONTACTED, EXPLAINED_AUTHORIZED, DEFERRED, ESCALATED_COUNSELING
    is_misconduct_charge = Column(Boolean, default=False, nullable=False)  # Strictly False: Advisory inquiry only, not misconduct
    disclaimer = Column(String(255), default="Advisory wellness inquiry only. Not a disciplinary finding or misconduct charge.", nullable=False)
    mentor_notes = Column(Text, nullable=True)
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    notification_id = Column(String(36), ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True)

    student = relationship("User", foreign_keys=[student_id], back_populates="mentor_alerts_for_student")
    mentor = relationship("User", foreign_keys=[mentor_id], back_populates="mentor_alerts_received")
    lecture_session = relationship("LectureSession")
    timetable_session = relationship("TimetableSession")
    notification = relationship("Notification", back_populates="mentor_alert")

class BiometricAccessLog(Base):
    __tablename__ = "biometric_access_logs"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    accessor_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(100), nullable=False)  # CAMPUS_IDENTITY_AND_ATTENDANCE_ONLY, ENROLLMENT, CONSENT_REVOCATION, ERASURE, BACKUP_TEST
    action = Column(String(50), nullable=False)  # DECRYPT_AND_MATCH, WRITE_TEMPLATE, REVOKE_CONSENT, CRYPTOGRAPHIC_ERASURE
    status = Column(String(50), nullable=False, default="AUTHORIZED_SUCCESS")  # AUTHORIZED_SUCCESS, DENIED_UNAUTHORIZED, REVOKED_BLOCKED
    client_ip = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    raw_image_persisted = Column(Boolean, default=False, nullable=False)  # Strictly False: In-memory non-persistent processing
    accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    accessor = relationship("User", foreign_keys=[accessor_id], back_populates="biometric_access_logs_made")
    target_user = relationship("User", foreign_keys=[target_user_id], back_populates="biometric_access_logs_target")

class RetentionRunLog(Base):
    __tablename__ = "retention_run_logs"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    run_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    retention_threshold_days = Column(Integer, default=90, nullable=False)
    cutoff_date = Column(DateTime, nullable=False)
    verification_attempts_purged = Column(Integer, default=0, nullable=False)
    notifications_purged = Column(Integer, default=0, nullable=False)
    access_logs_purged = Column(Integer, default=0, nullable=False)
    total_records_purged = Column(Integer, default=0, nullable=False)
    compliance_cert_hash = Column(String(64), nullable=False)
    status = Column(String(50), default="COMPLETED", nullable=False)
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    run_by = relationship("User")

class BackupRecord(Base):
    __tablename__ = "backup_records"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    backup_filename = Column(String(255), nullable=False)
    backup_path = Column(String(500), nullable=False)
    size_bytes = Column(Integer, default=0, nullable=False)
    sha256_checksum = Column(String(64), nullable=False)
    encryption_cipher = Column(String(50), default="AES-256-GCM/FERNET", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_expired = Column(Boolean, default=False, nullable=False)
    recovery_tested = Column(Boolean, default=False, nullable=False)
    last_recovery_test_at = Column(DateTime, nullable=True)
    last_recovery_status = Column(String(50), nullable=True)

class MerkleCommitment(Base):
    __tablename__ = "merkle_commitments"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    day = Column(Date, nullable=False, index=True)
    merkle_root = Column(String(64), nullable=False, index=True)
    anchor_network = Column(String(50), default="ETHEREUM_SEPOLIA_ANCHOR", nullable=False)
    transaction_hash = Column(String(66), nullable=False)
    block_number = Column(Integer, nullable=False)
    event_count = Column(Integer, default=0, nullable=False)
    tree_depth = Column(Integer, default=0, nullable=False)
    leaf_hashes = Column(JSON, default=list, nullable=False)
    status = Column(String(50), default="ANCHORED_ON_CHAIN", nullable=False)
    anchored_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    anchored_by = relationship("User")

class AuditVerificationLog(Base):
    __tablename__ = "audit_verification_logs"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    verified_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verification_type = Column(String(50), default="CONSOLIDATED_FULL_AUDIT", nullable=False)
    attendance_chain_valid = Column(Boolean, default=True, nullable=False)
    gate_chain_valid = Column(Boolean, default=True, nullable=False)
    presence_chain_valid = Column(Boolean, default=True, nullable=False)
    overall_tamper_free = Column(Boolean, default=True, nullable=False)
    total_records_audited = Column(Integer, default=0, nullable=False)
    attendance_count = Column(Integer, default=0, nullable=False)
    gate_count = Column(Integer, default=0, nullable=False)
    presence_count = Column(Integer, default=0, nullable=False)
    tampered_records = Column(JSON, default=list, nullable=False)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    verified_by = relationship("User")

