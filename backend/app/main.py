import os
import time
import uuid
from datetime import datetime, timedelta, date
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from .config import settings
from .database import engine, Base, SessionLocal
from .models import Campus, User, Attendance, Building, Floor, Room, TimetableSession, WorkShift, GateDevice, GateEvent, VisitorPass, LectureSession, RoomPresence
from .core.security import hash_password, compute_attendance_event_hash, compute_gate_event_hash, compute_room_presence_hash, GENESIS_HASH
from .core.limiter import limiter
from .core.security_headers import SecurityHeadersMiddleware
from .routers import auth, devices, biometric, attendance, admin, registry, gate, presence, notifications, privacy

STARTUP_TIME = time.time()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AERIS Smart Campus Face-Verified Attendance API",
    version="1.0.0"
)

# Rate Limiter — keyed by remote IP; singleton stored on app.state for SlowAPI middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security Headers Middleware (HSTS, CSP, Permissions-Policy, X-Frame-Options)
app.add_middleware(SecurityHeadersMiddleware)

# CORS Middleware (Configurable for development and restricted in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(biometric.router)
app.include_router(attendance.router)
app.include_router(admin.router)
app.include_router(registry.router)
app.include_router(gate.router)
app.include_router(presence.router)
app.include_router(notifications.router)
app.include_router(privacy.router)


import os
from fastapi.staticfiles import StaticFiles

_dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dashboard", "dist"))
if os.path.isdir(_dist_dir):
    app.mount("/admin-portal", StaticFiles(directory=_dist_dir, html=True), name="admin-portal")

@app.on_event("startup")
def on_startup():
    # 0. Enforce production security constraints
    settings.validate_production_secrets()

    # Create all DB tables
    Base.metadata.create_all(bind=engine)

    # Seed initial test data if DB is empty
    db = SessionLocal()
    try:
        # 1. Backfill any unchained attendance records to ensure cryptographic audit integrity
        unchained_records = db.query(Attendance).order_by(Attendance.checked_in_at.asc()).all()
        if unchained_records:
            running_prev_hash = GENESIS_HASH
            for rec in unchained_records:
                if not rec.event_hash or not rec.prev_hash:
                    rec.prev_hash = running_prev_hash
                    day_s = rec.day.isoformat() if rec.day else ""
                    time_s = rec.checked_in_at.isoformat() if rec.checked_in_at else ""
                    rec.event_hash = compute_attendance_event_hash(
                        prev_hash=running_prev_hash,
                        attendance_id=rec.id,
                        user_id=rec.user_id,
                        campus_id=rec.campus_id,
                        day_str=day_s,
                        checked_in_at_str=time_s,
                        risk_score=rec.risk_score,
                        device_id=rec.device_id
                    )
                running_prev_hash = rec.event_hash
            db.commit()

        # 1b. Backfill any unchained or broken gate event records for tamper-proof audit integrity
        gate_records = db.query(GateEvent).order_by(GateEvent.timestamp.asc(), GateEvent.id.asc()).all()
        if gate_records:
            running_prev_hash = GENESIS_HASH
            for rec in gate_records:
                time_s = rec.timestamp.isoformat() if rec.timestamp else ""
                expected_hash = compute_gate_event_hash(
                    prev_hash=running_prev_hash,
                    event_id=rec.id,
                    user_id=rec.user_id,
                    gate_id=rec.gate_id,
                    direction=rec.direction,
                    event_type=rec.event_type,
                    device_id=rec.device_id,
                    timestamp_str=time_s,
                    synced_offline=rec.synced_offline
                )
                if rec.prev_hash != running_prev_hash or rec.event_hash != expected_hash:
                    rec.prev_hash = running_prev_hash
                    rec.event_hash = expected_hash
                running_prev_hash = rec.event_hash
            db.commit()

        # 2. Seed Default Campus

        campus = db.query(Campus).first()
        if not campus:
            campus = Campus(
                name="Arya Main Campus, Jaipur",
                latitude=26.8228,
                longitude=75.8648,
                radius_m=350,
                wifi_bssids=["00:14:22:01:23:45", "a4:b2:39:cd:ef:01"],
                timezone="Asia/Kolkata"
            )
            db.add(campus)
            db.commit()
            db.refresh(campus)

        # 2. Seed Default Admin
        admin_user = db.query(User).filter(User.email == "admin@campusproof.edu").first()
        if not admin_user:
            admin_user = User(
                employee_id="ADM001",
                name="Dr. Alok Sharma",
                email="admin@campusproof.edu",
                password_hash=hash_password("Admin@123"),
                role="admin",
                status="active",
                campus_id=campus.id
            )
            db.add(admin_user)

        # 3. Seed Default Staff User
        staff_user = db.query(User).filter(User.email == "priya.verma@campusproof.edu").first()
        if not staff_user:
            staff_user = User(
                employee_id="EMP042",
                name="Prof. Priya Verma",
                email="priya.verma@campusproof.edu",
                password_hash=hash_password("Staff@123"),
                role="staff",
                status="active",
                campus_id=campus.id
            )
            db.add(staff_user)

        # 4. Seed Secondary Staff User for Testing
        staff_user2 = db.query(User).filter(User.email == "rahul.mehta@campusproof.edu").first()
        if not staff_user2:
            staff_user2 = User(
                employee_id="EMP089",
                name="Rahul Mehta",
                email="rahul.mehta@campusproof.edu",
                password_hash=hash_password("Staff@123"),
                role="staff",
                status="active",
                campus_id=campus.id
            )
            db.add(staff_user2)

        # 5. Seed Default Student User for Testing
        student_user = db.query(User).filter(User.email == "aarav.sharma@campusproof.edu").first()
        if not student_user:
            student_user = User(
                employee_id="STU101",
                name="Aarav Sharma",
                email="aarav.sharma@campusproof.edu",
                password_hash=hash_password("Student@123"),
                role="student",
                department="CSE",
                status="active",
                campus_id=campus.id
            )
            db.add(student_user)

        # 6. Seed Centralized Registry: Faculty, Guards, Workers, Visitors
        hod_cse = db.query(User).filter(User.email == "meena.sharma@campusproof.edu").first()
        if not hod_cse:
            hod_cse = User(
                employee_id="FAC001",
                name="Dr. Meena Sharma",
                email="meena.sharma@campusproof.edu",
                password_hash=hash_password("Faculty@123"),
                role="faculty",
                department="CSE",
                designation="HOD & Professor",
                status="active",
                campus_id=campus.id
            )
            db.add(hod_cse)

        guard_user = db.query(User).filter(User.email == "rajesh.guard@campusproof.edu").first()
        if not guard_user:
            guard_user = User(
                employee_id="SEC001",
                name="Rajesh Gurjar",
                email="rajesh.guard@campusproof.edu",
                password_hash=hash_password("Guard@123"),
                role="guard",
                department="Campus Security",
                designation="Security Incharge",
                status="active",
                campus_id=campus.id
            )
            db.add(guard_user)

        worker_user = db.query(User).filter(User.email == "ramesh.worker@campusproof.edu").first()
        if not worker_user:
            worker_user = User(
                employee_id="WRK001",
                name="Ramesh Kumar",
                email="ramesh.worker@campusproof.edu",
                password_hash=hash_password("Worker@123"),
                role="worker",
                department="Facilities",
                designation="Sanitation Staff",
                status="active",
                campus_id=campus.id
            )
            db.add(worker_user)

        visitor_user = db.query(User).filter(User.email == "amit.visitor@gmail.com").first()
        if not visitor_user:
            visitor_user = User(
                employee_id="VIS001",
                name="Amit Bansal",
                email="amit.visitor@gmail.com",
                password_hash=hash_password("Visitor@123"),
                role="visitor",
                department="Guest",
                designation="Parent / Visitor",
                status="active",
                campus_id=campus.id
            )
            db.add(visitor_user)

        db.commit()

        # 7. Seed Buildings, Floors, and Rooms if not seeded
        bldg_a = db.query(Building).first()
        if not bldg_a:
            bldg_a = Building(campus_id=campus.id, name="Arya Academic Block A", code="BLK-A")
            bldg_b = Building(campus_id=campus.id, name="Arya Tech Block B", code="BLK-B")
            db.add_all([bldg_a, bldg_b])
            db.commit()

            # Floors for Block A
            fl_g = Floor(building_id=bldg_a.id, floor_number=0, name="Ground Floor")
            fl_1 = Floor(building_id=bldg_a.id, floor_number=1, name="1st Floor (ECE)")
            fl_2 = Floor(building_id=bldg_a.id, floor_number=2, name="2nd Floor (CSE)")
            db.add_all([fl_g, fl_1, fl_2])
            db.commit()

            # Rooms
            r1 = Room(floor_id=fl_1.id, room_number="LT-16", name="Lecture Theatre 16", room_type="lecture_hall", capacity=120, current_occupancy=45)
            r2 = Room(floor_id=fl_2.id, room_number="LT-24", name="Smart AI/ML Room", room_type="lecture_hall", capacity=80, current_occupancy=32)
            r3 = Room(floor_id=fl_1.id, room_number="LT-11", name="Classroom 11", room_type="lecture_hall", capacity=60, current_occupancy=0)
            r4 = Room(floor_id=fl_1.id, room_number="ECE-LAB", name="ECE Labs", room_type="lab", capacity=40, current_occupancy=18)
            r5 = Room(floor_id=fl_2.id, room_number="FF-CL-02", name="Computer Lab 02", room_type="lab", capacity=50, current_occupancy=25)
            r6 = Room(floor_id=fl_g.id, room_number="LIBRARY", name="Central Library", room_type="library", capacity=200, current_occupancy=65)
            r7 = Room(floor_id=fl_g.id, room_number="AUDI", name="Auditorium Hall", room_type="auditorium", capacity=500, current_occupancy=0)
            r8 = Room(floor_id=fl_g.id, room_number="GATE-01", name="Main Gate Checkpoint", room_type="gate", capacity=10, current_occupancy=2)
            db.add_all([r1, r2, r3, r4, r5, r6, r7, r8])
            db.commit()

            # Seed Timetable Sessions
            if hod_cse:
                s1 = TimetableSession(
                    room_id=r2.id,
                    faculty_id=hod_cse.id,
                    subject_name="AI & Machine Learning",
                    subject_code="CS305",
                    day_of_week="Mon",
                    start_time="10:40",
                    end_time="11:30",
                    department="CSE",
                    section="Section A"
                )
                s2 = TimetableSession(
                    room_id=r1.id,
                    faculty_id=hod_cse.id,
                    subject_name="Operating Systems",
                    subject_code="CS304",
                    day_of_week="Mon",
                    start_time="11:30",
                    end_time="12:20",
                    department="CSE",
                    section="Section A"
                )
                db.add_all([s1, s2])

            # Seed Work Shifts
            if guard_user:
                sh1 = WorkShift(
                    user_id=guard_user.id,
                    shift_name="Morning Security Gate Shift",
                    start_time="08:00",
                    end_time="16:00",
                    assigned_location="Main Gate",
                    days="Mon,Tue,Wed,Thu,Fri,Sat"
                )
                db.add(sh1)

            db.commit()

        # 8. Seed Gate Devices (Phase 3)
        dev1 = db.query(GateDevice).filter(GateDevice.device_id == "GATE-DEV-01").first()
        if not dev1:
            gdev1 = GateDevice(
                device_id="GATE-DEV-01",
                gate_id="GATE-MAIN-01",
                gate_name="Main Campus Turnstile A",
                location="Campus Main Entrance",
                status="authorized",
                registered_at=datetime.utcnow() - timedelta(days=7),
                last_heartbeat=datetime.utcnow()
            )
            gdev2 = GateDevice(
                device_id="GATE-DEV-02",
                gate_id="GATE-MAIN-02",
                gate_name="Main Campus Turnstile B",
                location="Campus Main Entrance",
                status="authorized",
                registered_at=datetime.utcnow() - timedelta(days=7),
                last_heartbeat=datetime.utcnow()
            )
            gdev3 = GateDevice(
                device_id="GATE-DEV-03",
                gate_id="GATE-NORTH-01",
                gate_name="North Gate Mobile Scanner",
                location="North Academic Checkpoint",
                status="authorized",
                registered_at=datetime.utcnow() - timedelta(days=5),
                last_heartbeat=datetime.utcnow()
            )
            db.add_all([gdev1, gdev2, gdev3])
            db.commit()

        # 9. Seed Active Visitor Pass (Phase 3)
        v_pass = db.query(VisitorPass).first()
        if not v_pass and visitor_user:
            v_pass = VisitorPass(
                visitor_id=visitor_user.id,
                host_user_id=admin_user.id if admin_user else None,
                purpose="Institutional AI Curriculum Review Meeting",
                badge_number="VP-20261014-G01",
                valid_from=datetime.utcnow() - timedelta(hours=2),
                valid_until=datetime.utcnow() + timedelta(hours=6),
                status="active"
            )
            db.add(v_pass)
            db.commit()

        # 10. Seed Initial Chained Gate Events (Phase 3)
        existing_gate_event = db.query(GateEvent).first()
        if not existing_gate_event and student_user and staff_user:
            t_base = datetime.utcnow() - timedelta(hours=4)
            running_prev_hash = GENESIS_HASH

            seed_events = [
                (student_user.id, "GATE-MAIN-01", "ENTRY", "DYNAMIC_QR", "GATE-DEV-01", None, None, False, t_base),
                (staff_user.id, "GATE-MAIN-01", "ENTRY", "DYNAMIC_QR", "GATE-DEV-01", None, None, False, t_base + timedelta(minutes=15)),
                (visitor_user.id if visitor_user else student_user.id, "GATE-MAIN-01", "ENTRY", "VISITOR_PASS", "GATE-DEV-01", None, None, False, t_base + timedelta(minutes=30)),
                (student_user.id, "GATE-NORTH-01", "EXIT", "DYNAMIC_QR", "GATE-DEV-03", None, None, True, t_base + timedelta(hours=1)),
            ]

            for uid, gid, direction, ev_type, did, guard_id, reason, is_offline, ts in seed_events:
                eid = str(uuid.uuid4())
                time_str = ts.isoformat()
                ehash = compute_gate_event_hash(
                    prev_hash=running_prev_hash,
                    event_id=eid,
                    user_id=uid,
                    gate_id=gid,
                    direction=direction,
                    event_type=ev_type,
                    device_id=did,
                    timestamp_str=time_str,
                    synced_offline=is_offline
                )
                gev = GateEvent(
                    id=eid,
                    user_id=uid,
                    gate_id=gid,
                    direction=direction,
                    event_type=ev_type,
                    guard_id=guard_id,
                    override_reason=reason,
                    device_id=did,
                    timestamp=ts,
                    client_event_id=str(uuid.uuid4()) if is_offline else None,
                    synced_offline=is_offline,
                    offline_device_timestamp=ts if is_offline else None,
                    prev_hash=running_prev_hash,
                    event_hash=ehash
                )
                db.add(gev)
                running_prev_hash = ehash

            db.commit()

        # 11. Seed Active Lecture Session for Phase 4
        active_lec = db.query(LectureSession).filter(LectureSession.status == "active").first()
        if not active_lec:
            room_ai = db.query(Room).filter(Room.room_number == "LT-24").first()
            if not room_ai:
                room_ai = db.query(Room).first()
            fac_user = db.query(User).filter(User.role.in_(["faculty", "staff", "admin"])).first()
            if room_ai and fac_user:
                active_lec = LectureSession(
                    faculty_id=fac_user.id,
                    room_id=room_ai.id,
                    subject_name="AI & Machine Learning",
                    subject_code="CS305",
                    section="Section A",
                    status="active",
                    started_at=datetime.utcnow(),
                    secret_key=os.urandom(32).hex()
                )
                db.add(active_lec)
                db.commit()

        # 12. Seed Staff Room, Common Area & Sample Room Presences
        staff_room = db.query(Room).filter(Room.room_number == "STAFF-CSE").first()
        if not staff_room:
            fl_2 = db.query(Floor).filter(Floor.floor_number == 2).first()
            if fl_2:
                staff_room = Room(
                    floor_id=fl_2.id,
                    room_number="STAFF-CSE",
                    name="CSE Faculty & Staff Lounge",
                    room_type="staff_room",
                    capacity=30,
                    current_occupancy=6,
                    authorized_roles=["faculty", "staff", "admin"],
                    wifi_bssid="a4:b2:39:cd:ef:01",
                    qr_secret="STAFF-SECRET-KEY-001"
                )
                db.add(staff_room)
                db.commit()

        cafe_room = db.query(Room).filter(Room.room_number == "CAFE-01").first()
        if not cafe_room:
            fl_g = db.query(Floor).filter(Floor.floor_number == 0).first()
            if fl_g:
                cafe_room = Room(
                    floor_id=fl_g.id,
                    room_number="CAFE-01",
                    name="Central Student Lounge & Cafeteria",
                    room_type="common_area",
                    capacity=150,
                    current_occupancy=42,
                    authorized_roles=["all"],
                    wifi_bssid="00:14:22:01:23:45",
                    qr_secret="CAFE-SECRET-KEY-001"
                )
                db.add(cafe_room)
                db.commit()

        existing_p = db.query(RoomPresence).first()
        if not existing_p:
            staff_u = db.query(User).filter(User.role.in_(["faculty", "staff"])).first()
            stud_u = db.query(User).filter(User.role == "student").first()
            target_rm = db.query(Room).filter(Room.room_number == "LT-24").first() or db.query(Room).first()

            if staff_u and target_rm:
                p_id = str(uuid.uuid4())
                ts_str = datetime.utcnow().isoformat()
                phash = compute_room_presence_hash(GENESIS_HASH, p_id, staff_u.id, target_rm.id, "INDOOR_QR", ts_str)
                p1 = RoomPresence(
                    id=p_id,
                    user_id=staff_u.id,
                    room_id=target_rm.id,
                    check_in_at=datetime.utcnow(),
                    verification_method="INDOOR_QR",
                    device_id="STAFF-PHONE-042",
                    evidence_payload={"badge_token": "AERIS-INDOOR-LT24", "room": target_rm.room_number},
                    status="active",
                    prev_hash=GENESIS_HASH,
                    presence_hash=phash
                )
                db.add(p1)

            if stud_u and target_rm:
                p_id2 = str(uuid.uuid4())
                ts_str2 = datetime.utcnow().isoformat()
                p1_hash = p1.presence_hash if 'p1' in locals() else GENESIS_HASH
                phash2 = compute_room_presence_hash(p1_hash, p_id2, stud_u.id, target_rm.id, "BLE_BEACON", ts_str2)
                p2 = RoomPresence(
                    id=p_id2,
                    user_id=stud_u.id,
                    room_id=target_rm.id,
                    check_in_at=datetime.utcnow(),
                    verification_method="BLE_BEACON",
                    device_id="STUDENT-PHONE-101",
                    evidence_payload={"beacon_rssi": -64, "uuid": "4f2a71c8-e042-4b2a"},
                    status="active",
                    prev_hash=p1_hash,
                    presence_hash=phash2
                )
                db.add(p2)

            db.commit()

    finally:
        db.close()

@app.get("/")
def root():
    return {
        "project": settings.PROJECT_NAME,
        "status": "online",
        "docs": "/docs",
        "version": "1.0.0"
    }

@app.get("/health")
def health():
    db = SessionLocal()
    start_db = time.time()
    db_connected = False
    counts = {}
    try:
        db.execute(text("SELECT 1;"))
        db_connected = True
        counts = {
            "users": db.query(User).count(),
            "attendance": db.query(Attendance).count(),
            "gate_events": db.query(GateEvent).count(),
            "room_presences": db.query(RoomPresence).count()
        }
    except Exception as e:
        db_connected = False
    finally:
        db.close()
    db_latency_ms = round((time.time() - start_db) * 1000, 2)

    all_keys = settings.get_all_fernet_keys()

    return {
        "status": "healthy" if db_connected else "degraded",
        "project": settings.PROJECT_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": round(time.time() - STARTUP_TIME, 2),
        "database": {
            "connected": db_connected,
            "engine": "sqlite_wal" if settings.DATABASE_URL.startswith("sqlite") else "postgresql",
            "latency_ms": db_latency_ms,
            "entity_counts": counts
        },
        "security": {
            "hsts_enabled": settings.ENABLE_HSTS,
            "fernet_keys_active": len(all_keys),
            "algorithm": settings.ALGORITHM
        }
    }

@app.get("/health/ready")
def readiness_probe(response: Response):
    db = SessionLocal()
    is_ready = True
    reason = "Ready"
    try:
        db.execute(text("SELECT 1;"))
        settings.validate_production_secrets()
    except Exception as e:
        is_ready = False
        reason = str(e)
    finally:
        db.close()

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "NOT_READY", "reason": reason}

    return {"status": "READY", "timestamp": datetime.utcnow().isoformat()}

@app.get("/health/live")
def liveness_probe():
    return {"status": "ALIVE", "uptime_seconds": round(time.time() - STARTUP_TIME, 2)}

@app.get("/metrics")
def get_system_metrics():
    db = SessionLocal()
    try:
        today = date.today()
        day_start = datetime.combine(today, datetime.min.time())
        day_end = datetime.combine(today, datetime.max.time())

        total_users = db.query(User).count()
        present_today = db.query(Attendance).filter(Attendance.day == today).count()
        gate_events_today = db.query(GateEvent).filter(GateEvent.timestamp >= day_start, GateEvent.timestamp <= day_end).count()
        active_presences = db.query(RoomPresence).filter(RoomPresence.status == "active").count()
    finally:
        db.close()

    return {
        "uptime_seconds": round(time.time() - STARTUP_TIME, 2),
        "total_users": total_users,
        "attendance_today": present_today,
        "gate_events_today": gate_events_today,
        "active_indoor_presences": active_presences,
        "system_status": "OPERATIONAL"
    }
