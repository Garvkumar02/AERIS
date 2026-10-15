from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime

# ==========================================
# Authentication & Registration
# ==========================================

class LoginRequest(BaseModel):
    email: str
    password: str

class StudentRegistrationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    employee_id: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    role: Optional[str] = "student"
    department: Optional[str] = "CSE"
    designation: Optional[str] = None
    status: Optional[str] = "active"

class LoginResponse(BaseModel):
    token: str
    role: str
    name: str
    employee_id: str
    department: Optional[str] = None
    designation: Optional[str] = None
    user_id: Optional[str] = None

# ==========================================
# Centralized Registry (People Management)
# ==========================================

class UserCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    employee_id: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    role: str = Field(default="student")  # student, faculty, staff, guard, worker, visitor, admin
    department: Optional[str] = "CSE"
    designation: Optional[str] = None
    phone: Optional[str] = None

class UserUpdateRequest(BaseModel):
    employee_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None

class UserStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(active|suspended|revoked)$")

class UserResponse(BaseModel):
    id: str
    employee_id: str
    name: str
    email: str
    role: str
    department: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    biometric_enrolled: bool = False

# ==========================================
# Device
# ==========================================

class DeviceRegisterRequest(BaseModel):
    device_id: str
    platform: Optional[str] = "android"

class DeviceRegisterResponse(BaseModel):
    status: str

# ==========================================
# Biometric Verification & Revocation
# ==========================================

class BiometricEnrollResponse(BaseModel):
    enrolled: bool
    model_version: str

class BiometricRevokeResponse(BaseModel):
    revoked: bool
    user_id: str
    revoked_at: str
    message: str

class SessionResponse(BaseModel):
    session_id: str
    challenge: str  # "TURN_LEFT" | "TURN_RIGHT"
    expires_in: int

class VerifyResponse(BaseModel):
    result: str  # "ACCEPT" | "REJECT" | "ALREADY_MARKED"
    code: Optional[str] = None
    message: str

class MyAttendanceItem(BaseModel):
    day: str
    checked_in_at: str
    risk_score: Optional[int] = None

# ==========================================
# Spatial & Campus Infrastructure
# ==========================================

class RoomResponse(BaseModel):
    id: str
    room_number: str
    name: str
    room_type: str
    capacity: int
    current_occupancy: int
    floor_id: str
    floor_name: Optional[str] = None

class RoomCreateRequest(BaseModel):
    floor_id: str
    room_number: str
    name: str
    room_type: str = "lecture_hall"
    capacity: int = 60

class FloorResponse(BaseModel):
    id: str
    floor_number: int
    name: str
    building_id: str
    rooms: List[RoomResponse] = []

class BuildingResponse(BaseModel):
    id: str
    name: str
    code: str
    floors: List[FloorResponse] = []

class TimetableSessionResponse(BaseModel):
    id: str
    subject_name: str
    subject_code: str
    day_of_week: str
    start_time: str
    end_time: str
    department: str
    section: str
    room_number: str
    room_name: str
    faculty_name: str

class TimetableSessionCreate(BaseModel):
    room_id: str
    faculty_id: str
    subject_name: str
    subject_code: str
    day_of_week: str
    start_time: str
    end_time: str
    department: str = "CSE"
    section: str = "Section A"

class WorkShiftResponse(BaseModel):
    id: str
    shift_name: str
    start_time: str
    end_time: str
    assigned_location: str
    days: str
    user_name: str
    user_role: str

# ==========================================
# Admin Endpoints & Analytics
# ==========================================

class AdminPresentItem(BaseModel):
    employee_id: str
    name: str
    role: Optional[str] = "staff"
    department: Optional[str] = None
    checked_in_at: str
    risk_score: Optional[int] = None

class AdminAbsentItem(BaseModel):
    employee_id: str
    name: str
    role: Optional[str] = "staff"
    department: Optional[str] = None

class AdminAttendanceResponse(BaseModel):
    present: List[AdminPresentItem]
    absent: List[AdminAbsentItem]

class AdminAttemptItem(BaseModel):
    created_at: str
    name: str
    result: str
    failure_code: Optional[str] = None
    face_score: Optional[float] = None
    distance_m: Optional[float] = None
    device_id: Optional[str] = None

class AdminStatsResponse(BaseModel):
    total_staff: int
    present_today: int
    absent_today: int
    rejections_today: int
    reasons: Dict[str, int]
    hourly: Dict[str, int]

class CampusResponse(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_m: int
    timezone: str

class CampusUpdateRequest(BaseModel):
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_m: Optional[int] = None

class DashboardOverviewMetrics(BaseModel):
    total_students: int
    total_faculty: int
    total_employees: int
    today_classes: int
    present_today_pct: int
    room_utilization_pct: int
    security_alerts_count: int
    pending_requests_count: int
    department_attendance: Dict[str, int]

# ==========================================
# Phase 3: Gate Access, Dynamic QR & Offline Sync
# ==========================================

class DynamicQRTokenResponse(BaseModel):
    token: str
    seconds_remaining: int
    rotation_interval: int = 12
    expires_at: int
    nonce: str
    user_id: str
    name: str
    role: str
    employee_id: str

class VerifyQRRequest(BaseModel):
    qr_token: str
    device_id: str
    direction: str = Field(default="ENTRY", pattern="^(ENTRY|EXIT)$")
    gate_id: Optional[str] = "GATE-MAIN-01"

class GateVerifyResponse(BaseModel):
    result: str  # ACCESS_GRANTED | ACCESS_DENIED
    code: Optional[str] = None
    message: str
    direction: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    event_id: Optional[str] = None
    event_hash: Optional[str] = None
    timestamp: Optional[str] = None

class VisitorPassCreateRequest(BaseModel):
    visitor_name: str = Field(min_length=2, max_length=255)
    visitor_email: Optional[str] = None
    visitor_phone: Optional[str] = None
    host_employee_id: Optional[str] = None
    purpose: str = Field(min_length=3, max_length=255)
    badge_number: Optional[str] = None
    valid_duration_hours: Optional[int] = 8

class VisitorPassResponse(BaseModel):
    id: str
    badge_number: str
    visitor_id: str
    visitor_name: str
    visitor_email: Optional[str] = None
    visitor_phone: Optional[str] = None
    host_name: Optional[str] = None
    purpose: str
    valid_from: str
    valid_until: str
    status: str

class VerifyVisitorPassRequest(BaseModel):
    badge_number: str
    device_id: str
    direction: str = Field(default="ENTRY", pattern="^(ENTRY|EXIT)$")
    gate_id: Optional[str] = "GATE-MAIN-01"

class GuardOverrideRequest(BaseModel):
    target_identifier: str  # employee_id, email, or user_id
    direction: str = Field(default="ENTRY", pattern="^(ENTRY|EXIT)$")
    reason: str = Field(min_length=3, max_length=255)
    device_id: str
    gate_id: Optional[str] = "GATE-MAIN-01"

class GateDeviceRegisterRequest(BaseModel):
    device_id: str = Field(min_length=3, max_length=100)
    gate_id: str = Field(min_length=2, max_length=50)
    gate_name: str = Field(min_length=2, max_length=150)
    location: Optional[str] = "Main Campus Entry"
    status: Optional[str] = "authorized"

class GateDeviceResponse(BaseModel):
    id: str
    device_id: str
    gate_id: str
    gate_name: str
    location: Optional[str] = None
    status: str
    registered_at: Optional[str] = None
    last_heartbeat: Optional[str] = None

class GateDeviceStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(authorized|revoked|maintenance)$")

class GateDeviceHeartbeatRequest(BaseModel):
    device_id: str
    battery_pct: Optional[int] = None
    cached_events_count: Optional[int] = 0

class OfflineGateEventItem(BaseModel):
    client_event_id: str
    target_identifier: str  # employee_id or user_id
    direction: str = Field(default="ENTRY", pattern="^(ENTRY|EXIT)$")
    event_type: str = "OFFLINE_SYNC"  # DYNAMIC_QR, VISITOR_PASS, GUARD_OVERRIDE, OFFLINE_SYNC
    offline_device_timestamp: str
    guard_identifier: Optional[str] = None
    override_reason: Optional[str] = None

class OfflineSyncRequest(BaseModel):
    device_id: str
    gate_id: str
    events: List[OfflineGateEventItem]

class OfflineSyncResponse(BaseModel):
    status: str
    device_id: str
    total_received: int
    synced: int
    duplicates_skipped: int
    errors: int
    synced_at: str

class GateEventItemResponse(BaseModel):
    id: str
    client_event_id: Optional[str] = None
    user_id: str
    user_name: str
    employee_id: str
    user_role: str
    department: Optional[str] = None
    gate_id: str
    direction: str
    event_type: str
    guard_name: Optional[str] = None
    override_reason: Optional[str] = None
    device_id: str
    timestamp: str
    synced_offline: bool
    offline_device_timestamp: Optional[str] = None
    prev_hash: Optional[str] = None
    event_hash: str

class GateStatsResponse(BaseModel):
    total_entries_today: int
    total_exits_today: int
    current_on_campus: int
    active_visitor_passes: int
    authorized_devices_count: int
    offline_synced_count_today: int
    guard_overrides_today: int
    hourly_entries: Dict[str, int]
    hourly_exits: Dict[str, int]

class GateAuditIntegrityResponse(BaseModel):
    chain_valid: bool
    total_records: int
    genesis_hash: str
    latest_hash: str
    tampered_records: List[Dict[str, Any]]
    verified_at: str

# ==========================================
# Phase 4: Lecture Attendance & Double Verification
# ==========================================

class StartLectureRequest(BaseModel):
    timetable_session_id: Optional[str] = None
    subject_name: str = Field(min_length=2, max_length=150)
    subject_code: str = Field(min_length=2, max_length=50)
    room_id: str
    section: Optional[str] = "Section A"

class LectureSessionResponse(BaseModel):
    id: str
    timetable_session_id: Optional[str] = None
    subject_name: str
    subject_code: str
    section: str
    faculty_id: str
    faculty_name: str
    room_id: str
    room_number: str
    room_name: str
    status: str  # active, ended
    started_at: str
    ended_at: Optional[str] = None
    attendees_count: int = 0

class LectureQRResponse(BaseModel):
    token: str
    seconds_remaining: int
    rotation_interval: int
    expires_at: int
    nonce: str
    lecture_id: str
    room_id: str
    subject_code: str

class DoubleVerifyResponse(BaseModel):
    result: str  # ACCEPT | REJECT | DUPLICATE_ATTENDANCE
    code: Optional[str] = None
    message: str
    confirmation: Optional[Dict[str, Any]] = None

class AttendanceRecordResponse(BaseModel):
    id: str
    user_id: str
    student_name: str
    roll_number: str
    department: Optional[str] = None
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    room_number: Optional[str] = None
    day: str
    checked_in_at: str
    verification_method: str
    face_score: Optional[float] = None
    distance_m: Optional[float] = None
    os_biometric_verified: bool
    risk_score: Optional[int] = None
    event_hash: Optional[str] = None

class AttendanceAnalyticsResponse(BaseModel):
    total_recorded_today: int
    present_rate_pct: float
    debarment_risk_count: int
    debarment_risk_students: List[Dict[str, Any]]
    subject_percentages: Dict[str, float]

# ==========================================
# Floor-wise Presence & Common Rooms Schemas
# ==========================================

class RoomCheckInRequest(BaseModel):
    room_id: str
    user_id: Optional[str] = None
    verification_method: str = Field(default="INDOOR_QR", pattern="^(INDOOR_QR|BLE_BEACON|WIFI_BSSID|RFID_NFC|FACIAL_KIOSK|MANUAL_OVERRIDE)$")
    evidence_payload: Optional[Dict[str, Any]] = None
    device_id: Optional[str] = "DEVICE-DEFAULT"

class RoomCheckOutRequest(BaseModel):
    room_id: Optional[str] = None
    user_id: Optional[str] = None

class ConfirmedAttendeeItem(BaseModel):
    id: str
    user_id: str
    name: str
    employee_id: str
    role: str
    department: Optional[str] = None
    check_in_at: str
    verification_method: str

class RoomOccupancyStatusResponse(BaseModel):
    room_id: str
    room_number: str
    room_name: str
    room_type: str
    floor_id: str
    floor_name: str
    floor_number: int
    capacity: int
    confirmed_presence: int
    estimated_occupancy: int
    occupancy_rate_pct: float
    status: str  # Vacant, Optimal, Crowded, Over Capacity
    scheduled_class: Optional[Dict[str, Any]] = None
    confirmed_attendees: List[ConfirmedAttendeeItem] = []

class FloorPresenceSummaryResponse(BaseModel):
    floor_id: str
    floor_number: int
    floor_name: str
    building_name: str
    total_confirmed_presence: int
    total_estimated_occupancy: int
    total_capacity: int
    occupancy_rate_pct: float
    density_status: str  # Low, Moderate, High, Critical
    rooms: List[RoomOccupancyStatusResponse]

class RoomPresenceReceiptResponse(BaseModel):
    status: str
    message: str
    presence_id: str
    room_id: str
    room_number: str
    room_name: str
    floor_name: str
    user_name: str
    check_in_at: str
    verification_method: str
    presence_hash: str

# ==========================================
# Phase 6: Notifications & Mentor Alerts Schemas
# ==========================================

class NotificationResponse(BaseModel):
    id: str
    recipient_id: str
    recipient_name: Optional[str] = None
    recipient_role: Optional[str] = None
    category: str
    title: str
    message: str
    priority: str = "NORMAL"
    channel: str = "IN_APP"
    delivery_status: str = "PENDING"
    retry_count: int = 0
    max_retries: int = 3
    last_attempt_at: Optional[str] = None
    delivered_at: Optional[str] = None
    read_at: Optional[str] = None
    is_read: bool = False
    dedup_key: Optional[str] = None
    metadata_payload: Optional[Dict[str, Any]] = None
    created_at: str

class RescheduleClassRequest(BaseModel):
    subject_code: str
    section: Optional[str] = "Section A"
    original_time: str
    new_time: str
    new_date: str
    reason: Optional[str] = "Academic schedule update"

class RoomChangeAlertRequest(BaseModel):
    subject_code: str
    section: Optional[str] = "Section A"
    original_room: str
    new_room: str
    new_floor: Optional[str] = "Floor 1"
    reason: Optional[str] = "Venue maintenance / audio setup"

class ExamAlertRequest(BaseModel):
    subject_code: str
    subject_name: str
    exam_title: str
    exam_date: str
    start_time: str
    end_time: str
    room_number: str
    hall_ticket_info: Optional[str] = None
    invigilator: Optional[str] = None

class MentorAlertResponse(BaseModel):
    id: str
    student_id: str
    student_name: str
    student_roll: str
    student_department: Optional[str] = None
    mentor_id: str
    mentor_name: str
    subject_name: str
    subject_code: str
    room_number: Optional[str] = None
    absence_duration_minutes: int
    gate_presence_status: str
    room_presence_status: str
    status: str
    is_misconduct_charge: bool = False
    disclaimer: str
    mentor_notes: Optional[str] = None
    triggered_at: str
    resolved_at: Optional[str] = None
    notification_id: Optional[str] = None

class UpdateMentorAlertStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(ADVISORY_PENDING|STUDENT_CONTACTED|EXPLAINED_AUTHORIZED|DEFERRED|ESCALATED_COUNSELING)$")
    mentor_notes: Optional[str] = None

class BroadcastAlertResponse(BaseModel):
    status: str
    recipients_count: int
    suppressed_count: int
    category: str
    message: str
    notifications: List[NotificationResponse]

class CheckAbsenceAlertsResponse(BaseModel):
    lectures_checked: int
    alerts_generated: int
    alerts: List[MentorAlertResponse]

# ==========================================
# Phase 7: Privacy, Image Security & Retention Schemas
# ==========================================

class PrivacyConsentStatusResponse(BaseModel):
    user_id: str
    employee_id: str
    name: str
    role: str
    consent_status: str
    has_active_embedding: bool
    purpose_limitation: str
    storage_classification: str
    encryption_algorithm: str
    raw_image_persisted: bool = False
    consent_version: str
    enrolled_at: Optional[str] = None
    revoked_at: Optional[str] = None
    disclaimer: str

class GrantConsentRequest(BaseModel):
    consent_version: Optional[str] = "1.0"
    consent: bool = True

class RevokeConsentRequest(BaseModel):
    target_user_id: Optional[str] = None
    reason: Optional[str] = "User self-revocation"

class ErasureReceiptResponse(BaseModel):
    status: str
    user_id: str
    employee_id: str
    name: str
    deletion_receipt_hash: str
    erased_at: str
    regulatory_compliance: List[str]
    message: str

class BiometricAccessLogResponse(BaseModel):
    id: str
    accessor_id: str
    target_user_id: str
    purpose: str
    action: str
    status: str
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    raw_image_persisted: bool = False
    accessed_at: str

class RetentionStatusResponse(BaseModel):
    retention_policy_days: int
    cutoff_date: str
    eligible_records: Dict[str, int]
    last_retention_run: Optional[Dict[str, Any]] = None
    policy_description: str

class RetentionCleanupResponse(BaseModel):
    status: str
    retention_run_id: str
    retention_threshold_days: int
    cutoff_date: str
    executed_at: str
    records_purged: Dict[str, int]
    compliance_certificate: Dict[str, str]

class BackupRecordResponse(BaseModel):
    id: str
    backup_filename: str
    size_bytes: int
    sha256_checksum: str
    encryption_cipher: str
    created_at: str
    expires_at: str
    is_expired: bool
    recovery_tested: bool
    last_recovery_test_at: Optional[str] = None
    last_recovery_status: Optional[str] = None

class RecoveryTestReportResponse(BaseModel):
    status: str
    backup_id: str
    backup_filename: str
    integrity_check: str
    duration_ms: float
    verified_entity_counts: Dict[str, int]
    tested_at: str
    disaster_recovery_certified: bool

# ==========================================
# Phase 8: Admin Dashboard & Integrity Reports
# ==========================================

class AttendanceReportItem(BaseModel):
    id: str
    employee_id: str
    name: str
    role: str
    department: str
    day: str
    checked_in_at: str
    verification_method: str
    room_name: str
    floor_name: str
    face_score: Optional[float] = None
    risk_score: int
    event_hash: str
    status: str

class GateReportItem(BaseModel):
    id: str
    employee_id: str
    name: str
    role: str
    department: str
    gate_id: str
    gate_name: str
    direction: str
    event_type: str
    timestamp: str
    synced_offline: bool
    event_hash: str

class StaffDutyReportItem(BaseModel):
    shift_id: str
    employee_id: str
    name: str
    role: str
    department: str
    shift_name: str
    start_time: str
    end_time: str
    assigned_location: str
    scheduled_days: str
    duty_date: str
    checked_in_at: str
    duty_status: str

class VerificationReportItem(BaseModel):
    id: str
    employee_id: str
    name: str
    role: str
    department: str
    result: str
    failure_code: str
    face_score: Optional[float] = None
    distance_m: Optional[float] = None
    device_id: str
    created_at: str

class ConsolidatedIntegrityResponse(BaseModel):
    audit_id: str
    attendance_chain_valid: bool
    gate_chain_valid: bool
    presence_chain_valid: bool
    overall_tamper_free: bool
    total_records_audited: int
    attendance_count: int
    gate_count: int
    presence_count: int
    tampered_records: List[Dict[str, Any]]
    details: Dict[str, Any]
    verified_at: str

class AuditLogSummaryItem(BaseModel):
    id: str
    verification_type: str
    overall_tamper_free: bool
    total_records_audited: int
    attendance_chain_valid: bool
    gate_chain_valid: bool
    presence_chain_valid: bool
    tampered_count: int
    created_at: str

class MerkleAnchorRequest(BaseModel):
    day: Optional[str] = None  # YYYY-MM-DD, defaults to today
    network: Optional[str] = "ETHEREUM_SEPOLIA_ANCHOR"

class MerkleCommitmentResponse(BaseModel):
    id: str
    day: str
    merkle_root: str
    anchor_network: str
    transaction_hash: str
    block_number: int
    event_count: int
    tree_depth: int
    status: str
    created_at: str

class MerkleProofRequest(BaseModel):
    leaf_hash: str
    commitment_id: Optional[str] = None

class MerkleProofResponse(BaseModel):
    found: bool
    leaf_hash: str
    merkle_root: str
    commitment_id: Optional[str] = None
    anchor_network: Optional[str] = None
    transaction_hash: Optional[str] = None
    block_number: Optional[int] = None
    proof: List[Dict[str, str]]

class MerkleVerifyRequest(BaseModel):
    leaf_hash: str
    merkle_root: str
    proof: List[Dict[str, str]]

class MerkleVerifyResponse(BaseModel):
    verified: bool
    leaf_hash: str
    merkle_root: str
    proof_steps: int
    message: str

# ==========================================
# Webcam Live Face Attendance Schemas
# ==========================================

class WebcamVerifyResponse(BaseModel):
    result: str
    code: Optional[str] = None
    message: str
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    employee_id: Optional[str] = None
    department: Optional[str] = None
    similarity_score: Optional[float] = None
    confidence_pct: Optional[float] = None
    verification_method: Optional[str] = None
    attendance_id: Optional[str] = None
    ledger_hash: Optional[str] = None
    timestamp: Optional[str] = None
    vertices_count: Optional[int] = None
    yaw_deg: Optional[float] = None
    bbox: Optional[List[int]] = None
    landmarks: Optional[List[Dict[str, Any]]] = None
    key_vertices: Optional[Dict[str, List[int]]] = None
    ipd_px: Optional[float] = None

class WebcamEnrollResponse(BaseModel):
    status: str
    user_id: str
    name: str
    employee_id: str
    model_version: str
    message: str
    vertices_count: Optional[int] = None
    yaw_deg: Optional[float] = None
    bbox: Optional[List[int]] = None
    landmarks: Optional[List[Dict[str, Any]]] = None
    key_vertices: Optional[Dict[str, List[int]]] = None



