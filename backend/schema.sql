-- CampusProof PostgreSQL Database Schema (Section 7.2)

CREATE TABLE IF NOT EXISTS campuses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    radius_m INTEGER NOT NULL DEFAULT 300,
    wifi_bssids TEXT[] DEFAULT '{}',
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata'
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'staff', -- 'staff' | 'admin'
    status TEXT NOT NULL DEFAULT 'active',
    campus_id UUID REFERENCES campuses(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS biometric_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    encrypted_embedding BYTEA NOT NULL,
    model_version TEXT NOT NULL,
    consent_version TEXT NOT NULL,
    enrolled_at TIMESTAMPTZ DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    platform TEXT DEFAULT 'android',
    status TEXT DEFAULT 'active',
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, device_id)
);

CREATE TABLE IF NOT EXISTS attendance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    campus_id UUID REFERENCES campuses(id) ON DELETE SET NULL,
    day DATE NOT NULL,
    checked_in_at TIMESTAMPTZ DEFAULT NOW(),
    risk_score INTEGER,
    device_id TEXT,
    UNIQUE (user_id, day)
);

CREATE TABLE IF NOT EXISTS verification_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    result TEXT NOT NULL, -- ACCEPT | REJECT
    failure_code TEXT,
    face_score REAL,
    yaw_delta REAL,
    distance_m REAL,
    gps_accuracy REAL,
    is_mock BOOLEAN,
    device_id TEXT,
    risk_score INTEGER
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_id UUID,
    action TEXT,
    entity TEXT,
    entity_id TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    prev_hash VARCHAR(64),
    record_hash VARCHAR(64)
);

-- ========================================================
-- Phase 3: Gate Access, Dynamic QR & Offline Sync Schema
-- ========================================================

CREATE TABLE IF NOT EXISTS visitor_passes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    visitor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    host_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL,
    badge_number VARCHAR(50) UNIQUE NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS gate_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id VARCHAR(100) UNIQUE NOT NULL,
    gate_id VARCHAR(50) NOT NULL,
    gate_name VARCHAR(150) NOT NULL,
    location VARCHAR(150) DEFAULT 'Main Campus Entry',
    status VARCHAR(50) NOT NULL DEFAULT 'authorized', -- 'authorized' | 'revoked' | 'maintenance'
    api_key_hash VARCHAR(64),
    registered_at TIMESTAMPTZ DEFAULT NOW(),
    last_heartbeat TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS gate_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    gate_id VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL, -- 'ENTRY' | 'EXIT'
    event_type VARCHAR(50) NOT NULL, -- 'DYNAMIC_QR' | 'GUARD_OVERRIDE' | 'VISITOR_PASS' | 'OFFLINE_SYNC' | 'BIOMETRIC'
    guard_id UUID REFERENCES users(id) ON DELETE SET NULL,
    override_reason VARCHAR(255),
    device_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    client_event_id VARCHAR(64) UNIQUE,
    synced_offline BOOLEAN NOT NULL DEFAULT FALSE,
    offline_device_timestamp TIMESTAMPTZ,
    prev_hash VARCHAR(64),
    event_hash VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gate_events_user ON gate_events(user_id);
CREATE INDEX IF NOT EXISTS idx_gate_events_gate ON gate_events(gate_id);
CREATE INDEX IF NOT EXISTS idx_gate_events_time ON gate_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_gate_events_client_id ON gate_events(client_event_id);
CREATE INDEX IF NOT EXISTS idx_visitor_passes_badge ON visitor_passes(badge_number);
CREATE INDEX IF NOT EXISTS idx_gate_devices_dev_id ON gate_devices(device_id);

-- Phase 4 Lecture Attendance & Double Verification
CREATE TABLE IF NOT EXISTS lecture_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timetable_session_id UUID REFERENCES timetable_sessions(id) ON DELETE SET NULL,
    faculty_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    room_id UUID NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    subject_name VARCHAR(150) NOT NULL,
    subject_code VARCHAR(50) NOT NULL,
    section VARCHAR(50) NOT NULL DEFAULT 'Section A',
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- 'active' | 'ended'
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    secret_key VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lecture_sessions_faculty ON lecture_sessions(faculty_id);
CREATE INDEX IF NOT EXISTS idx_lecture_sessions_room ON lecture_sessions(room_id);
CREATE INDEX IF NOT EXISTS idx_lecture_sessions_status ON lecture_sessions(status);

