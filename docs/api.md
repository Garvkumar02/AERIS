# CampusProof / AERIS API Contract & Documentation

## Overview
CampusProof (SKIT023 / AERIS) is an enterprise-grade smart-campus access and identity system. All requests use HTTPS (or local HTTP during development) and, except `/auth/login`, require an HTTP Authorization header:
```
Authorization: Bearer <token>
```

---

## 1. Authentication & Security Endpoints

| Method | Path | Target Role | Request Format | Success Response |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/auth/login` | All | JSON: `{ "email": string, "password": string }` | `{ "token": string, "role": string, "name": string, "employee_id": string }` |
| **POST** | `/devices/register` | Staff/Student | JSON: `{ "device_id": string, "platform": string }` | `{ "status": "active" }` |
| **POST** | `/biometric/enroll` | Staff/Student | Multipart: `consent=true`, `front`, `left`, `right` | `{ "enrolled": true, "model_version": "buffalo_l" }` |
| **POST** | `/attendance/session`| Staff/Student | Empty / None | `{ "session_id": string, "challenge": "TURN_LEFT" \| "TURN_RIGHT", "expires_in": 60 }` |
| **POST** | `/attendance/verify` | Staff/Student | Multipart: `session_id`, `lat`, `lng`, `accuracy`, `is_mock`, `device_id`, frames | `{ "result": "ACCEPT" \| "REJECT" \| "ALREADY_MARKED", "code": string, "message": string }` |
| **GET** | `/admin/audit/verify-integrity` | Admin | None | `{ "chain_valid": boolean, "total_records": number, "genesis_hash": string, "latest_hash": string }` |

---

## 2. Phase 3: Gate Access, Dynamic QR & Turnstile Endpoints

| Method | Path | Target Role | Description / Request Format | Success Response |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/gate/my-qr` | All Active | Generates a 12-second rotating cryptographic QR token with HMAC-SHA256 signature and single-use anti-replay nonce. | `{ "token": string, "seconds_remaining": number, "rotation_interval": 12, "expires_at": number, "nonce": string, "user_id": string, "name": string, "role": string }` |
| **POST** | `/gate/verify-qr` | Gate Device / Turnstile | Verifies rotating token, anti-replay nonce, checks device authorization, logs chained SHA-256 event.<br>JSON: `{ "qr_token": string, "device_id": string, "direction": "ENTRY" \| "EXIT", "gate_id": string }` | `{ "result": "ACCESS_GRANTED" \| "ACCESS_DENIED", "direction": string, "user": { ... }, "event_id": string, "event_hash": string }` |
| **POST** | `/gate/visitor-passes` | Guard / Admin | Issues visitor pass with institutional host binding.<br>JSON: `{ "visitor_name": string, "visitor_email": string, "visitor_phone": string, "purpose": string, "valid_duration_hours": number }` | `{ "id": string, "badge_number": string, "visitor_name": string, "valid_from": string, "valid_until": string, "status": "active" }` |
| **GET** | `/gate/visitor-passes` | Guard / Admin | Lists active/historical visitor passes with search.<br>Query: `?status=active&search=Anand` | `[ { "badge_number": string, "visitor_name": string, "host_name": string, "valid_until": string, "status": string } ]` |
| **PUT** | `/gate/visitor-passes/{id}/checkout` | Guard / Admin | Checks out visitor pass, disabling turnstile access. | `{ "badge_number": string, "status": "checked_out" }` |
| **POST** | `/gate/verify-visitor-pass` | Gate Device | Optical scan of visitor badge at turnstile scanner.<br>JSON: `{ "badge_number": string, "device_id": string, "direction": "ENTRY" \| "EXIT" }` | `{ "result": "ACCESS_GRANTED", "direction": string, "user": { ... }, "event_hash": string }` |
| **POST** | `/gate/guard-override` | Guard / Admin | Authorizes manual entry/exit with required justification and creates tamper-proof audit log.<br>JSON: `{ "target_identifier": string, "direction": "ENTRY" \| "EXIT", "reason": string, "device_id": string }` | `{ "result": "ACCESS_GRANTED", "user": { "override_reason": string, "guard_name": string }, "event_hash": string }` |
| **POST** | `/gate/devices/register` | Admin | Registers hardware turnstile reader or optical scanner.<br>JSON: `{ "device_id": string, "gate_id": string, "gate_name": string, "location": string }` | `{ "device_id": string, "status": "authorized" }` |
| **GET** | `/gate/devices` | Guard / Admin | Lists registered gate devices, operational statuses, and heartbeats. | `[ { "device_id": string, "gate_name": string, "status": "authorized", "last_heartbeat": string } ]` |
| **PUT** | `/gate/devices/{id}/status` | Admin | Toggles device authorization state (`authorized`, `maintenance`, `revoked`).<br>JSON: `{ "status": "maintenance" }` | `{ "device_id": string, "status": "maintenance" }` |
| **POST** | `/gate/devices/heartbeat` | Hardware Gate | Gate hardware device ping to confirm connectivity.<br>JSON: `{ "device_id": string, "battery_pct": number }` | `{ "status": "online", "server_time": string }` |
| **POST** | `/gate/sync-offline` | Gate Device | Synchronizes buffered access records stored offline. Guarantees idempotency and deduplication via `client_event_id`.<br>JSON: `{ "device_id": string, "gate_id": string, "events": [ ... ] }` | `{ "status": "success", "total_received": number, "synced": number, "duplicates_skipped": number, "errors": number }` |
| **GET** | `/gate/offline-cache` | Gate Device | Downloads active user credentials and visitor pass whitelist for local turnstile offline verification.<br>Query: `?device_id=GATE-DEV-01` | `{ "active_users": [ ... ], "active_passes": [ ... ], "timestamp": string }` |
| **GET** | `/gate/events` | Guard / Admin | Searchable gate access ledger with filters (`gate_id`, `direction`, `event_type`, `search`, `limit`, `offset`). | `[ { "id": string, "timestamp": string, "user_name": string, "direction": "ENTRY", "event_type": "DYNAMIC_QR", "event_hash": string } ]` |
| **GET** | `/gate/stats` | Guard / Admin | Live campus gate analytics: today's entries, exits, headcount on campus, active visitor passes. | `{ "total_entries_today": number, "total_exits_today": number, "current_on_campus": number, "active_visitor_passes": number }` |
| **GET** | `/gate/audit/verify-integrity` | Admin | Cryptographically verifies sequential SHA-256 hash chaining of all gate transactions from genesis block to tip. | `{ "chain_valid": boolean, "total_records": number, "genesis_hash": string, "latest_hash": string, "tampered_records": [] }` |

---

## 3. Structured Reason Codes

These reason codes are shared and agreed across Backend, Mobile app, and Admin Dashboard:

| Code | Meaning Shown to User | Severity | Domain |
| :--- | :--- | :--- | :--- |
| `QR_TOKEN_EXPIRED` | Dynamic QR expired (12s rotation exceeded). Auto-refreshed. | Warning / Auto-Retry | Gate Access |
| `QR_TOKEN_ALREADY_USED` | Token already scanned. Replay attack blocked. | Error / Security | Gate Access |
| `INVALID_QR_SIGNATURE` | Cryptographic signature mismatch. Token rejected. | Error / Security | Gate Access |
| `PASS_NOT_FOUND` | Visitor badge number not registered in system. | Error / Registry | Visitor Passes |
| `PASS_EXPIRED` | Visitor pass duration has expired. | Warning / State | Visitor Passes |
| `PASS_CHECKED_OUT` | Visitor pass was checked out by security. | Error / State | Visitor Passes |
| `DEVICE_UNAUTHORIZED` | Gate hardware scanner revoked or in maintenance. | Error / Hardware | Gate Hardware |
| `USER_SUSPENDED` | Institutional user account is suspended. | Error / Account | Central Registry |
| `USER_REVOKED` | User credentials have been revoked. | Error / Account | Central Registry |
| `SESSION_EXPIRED` | Biometric verification session expired. | Warning / Retry | Biometrics |
| `DEVICE_NOT_REGISTERED` | This phone is not your registered device. | Error / Security | Device Binding |
| `MOCK_LOCATION` | Fake location detected. Mock location blocked. | Error / Security | Geofence |
| `OUTSIDE_CAMPUS` | You are outside the campus perimeter boundary. | Error / Location | Geofence |
| `FACE_MISMATCH` | Biometric embedding does not match enrolled profile. | Error / Security | Vision Engine |
| `LIVENESS_FAILED` | Head turn challenge failed or spoofing detected. | Error / Spoof | Liveness |

---

## 4. Cryptographic Hash Chain Formulas

### Attendance Ledger Chaining:
$$H_n = \text{SHA256}(H_{n-1} \parallel \text{id} \parallel \text{user\_id} \parallel \text{campus\_id} \parallel \text{day} \parallel \text{timestamp} \parallel \text{risk\_score} \parallel \text{device\_id})$$

### Gate Access Ledger Chaining:
$$H_n = \text{SHA256}(H_{n-1} \parallel \text{id} \parallel \text{user\_id} \parallel \text{gate\_id} \parallel \text{direction} \parallel \text{event\_type} \parallel \text{device\_id} \parallel \text{timestamp} \parallel \text{synced\_offline})$$

- Genesis hash ($H_0$): `0000000000000000000000000000000000000000000000000000000000000000` (64 zeroes).
- Any modification, insertion, deletion, or backdating changes all downstream hash pointers and is immediately detected by `/gate/audit/verify-integrity`.

---

## 5. Phase 4: Lecture Attendance & Double Verification Endpoints

| Method | Path | Target Role | Description / Request Format | Success Response |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/attendance/lecture/start` | Faculty / Admin | Starts live lecture session and initiates 12s rotating dynamic QR.<br>JSON: `{ "subject_name": string, "subject_code": string, "room_id": string, "section": string }` | `{ "id": string, "subject_name": string, "subject_code": string, "room_number": string, "status": "active", "started_at": string }` |
| **POST** | `/attendance/lecture/{id}/end` | Faculty / Admin | Concludes lecture session, disables QR tokens, and generates attendance stats. | `{ "id": string, "status": "ended", "ended_at": string, "attendees_count": number }` |
| **GET** | `/attendance/lecture/active` | All | Lists all currently active lectures on campus. | `[ { "id": string, "subject_name": string, "room_number": string, "status": "active", "attendees_count": number } ]` |
| **GET** | `/attendance/lecture/{id}/qr` | Projector / Display | Fetches rotating 12-second signed dynamic QR token with remaining seconds countdown and anti-replay nonce. | `{ "token": string, "seconds_remaining": number, "rotation_interval": 12, "expires_at": number, "nonce": string, "lecture_id": string }` |
| **GET** | `/attendance/lecture/{id}/attendees` | Faculty / Admin | Live stream of students verified in this lecture session. | `[ { "student_name": string, "roll_number": string, "checked_in_at": string, "verification_method": string, "event_hash": string } ]` |
| **POST** | `/attendance/verify-lecture` | Student | Double verification: 12-second rotating QR token + ArcFace face matching + liveness challenge + GPS geofence + OS biometric.<br>Multipart/Form: `lecture_id`, `qr_token`, `lat`, `lng`, `accuracy`, `is_mock`, `device_id`, `os_biometric_verified`, `demo_bypass_frames`, optional frames | `{ "result": "ACCEPT", "confirmation": { "status": "CONFIRMED", "student_name": string, "roll_number": string, "subject_name": string, "verification_hash": string, "double_verified": true } }` |
| **GET** | `/attendance/records` | Faculty / Admin | Searchable, filterable attendance records with face match score, distance, and hash. | `[ { "student_name": string, "roll_number": string, "subject_name": string, "verification_method": string, "face_score": number, "distance_m": number, "event_hash": string } ]` |
| **GET** | `/attendance/analytics` | Faculty / Admin | Attendance analytics: campus present rate, debarment watchlist (&lt;75%), and subject statistics. | `{ "total_recorded_today": number, "present_rate_pct": number, "debarment_risk_count": number, "debarment_risk_students": [ ... ], "subject_percentages": { ... } }` |

---

## 6. Floor-wise Presence & Common Rooms Endpoints

| Method | Path | Target Role | Description / Request Format | Success Response |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/presence/floors` | All Authenticated | Returns campus-wide floor-wise hierarchy with clear distinction between confirmed presence and estimated occupancy. | `[ { "floor_number": number, "floor_name": string, "total_confirmed_presence": number, "total_estimated_occupancy": number, "rooms": [ ... ] } ]` |
| **GET** | `/presence/room/{room_id}/status` | All Authenticated | Detailed room status, active roster of authenticated occupants, density level, and sensor telemetry. | `{ "room_number": string, "room_type": string, "confirmed_presence": number, "estimated_occupancy": number, "active_occupants": [ ... ] }` |
| **GET** | `/presence/room/{room_id}/qr` | Display / Admin | Generates 60-second rotating signed indoor room QR token (non-GPS validated check-in). | `{ "qr_token": string, "expires_in_seconds": number, "expires_at": number }` |
| **POST** | `/presence/check-in` | Student / Staff | Validated indoor check-in via Indoor QR, BLE Beacon, Wi-Fi BSSID, or RFID/NFC.<br>JSON: `{ "room_id": string, "verification_method": string, "evidence_payload": { ... }, "device_id": string }` | `{ "status": "CHECKED_IN", "room_number": string, "user_name": string, "verification_method": string, "evidence_hash": string }` |
| **POST** | `/presence/check-out` | Student / Staff | Records room departure, clears confirmed presence, and calculates duration. | `{ "status": "CHECKED_OUT", "duration_minutes": number, "message": string }` |

---

## 7. Phase 6: Notifications & Mentor Alerts Endpoints

| Method | Path | Target Role | Description / Request Format | Success Response |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/notifications/my` | All Authenticated | Fetches authenticated user's notification stream. | `[ { "id": string, "category": string, "title": string, "message": string, "delivery_status": "DELIVERED", "is_read": boolean } ]` |
| **POST** | `/notifications/{id}/read` | Recipient | Acknowledges and marks notification as read. | `{ "status": "success", "id": string, "read_at": string }` |
| **POST** | `/notifications/{id}/retry` | Admin / Dispatcher | Re-queues a failed or pending notification delivery with retry backoff. | `{ "status": "DELIVERED", "retry_count": number }` |
| **POST** | `/notifications/retry-failed` | Admin | Retries all pending and failed notifications across campus. | `{ "retried_count": number, "success_count": number, "failed_count": number }` |
| **POST** | `/notifications/broadcast/reschedule` | Faculty / Admin | Broadcasts class rescheduling notices with duplicate suppression.<br>JSON: `{ "subject_code": string, "section": string, "original_time": string, "new_time": string, "new_date": string, "reason": string }` | `{ "status": "success", "recipients_count": number, "suppressed_count": number }` |
| **POST** | `/notifications/broadcast/room-change` | Faculty / Admin | Broadcasts classroom relocation notices with duplicate suppression.<br>JSON: `{ "subject_code": string, "section": string, "original_room": string, "new_room": string, "new_floor": string, "reason": string }` | `{ "status": "success", "recipients_count": number, "suppressed_count": number }` |
| **POST** | `/notifications/broadcast/exam-alert` | Academic Admin | Broadcasts examination alerts and hall venue details.<br>JSON: `{ "subject_code": string, "exam_title": string, "exam_date": string, "start_time": string, "end_time": string, "room_number": string }` | `{ "status": "success", "recipients_count": number, "suppressed_count": number }` |
| **POST** | `/notifications/check-absences` | Admin / System Cron | Scans active lectures, detects verified absences &gt;10 min, and generates advisory mentor alerts.<br>Query: `?min_absence_minutes=10` | `{ "status": "success", "lectures_checked": number, "alerts_generated": number }` |
| **GET** | `/notifications/mentor/alerts` | Faculty Mentor / Admin | Lists mentor advisory absence alerts cross-referencing campus gate entry and room status. | `[ { "id": string, "student_name": string, "student_roll": string, "absence_duration_minutes": number, "gate_presence_status": string, "is_misconduct_charge": false, "disclaimer": string, "status": string } ]` |
| **POST** | `/notifications/mentor/alerts/{id}/update-status` | Faculty Mentor | Updates pastoral inquiry status and logs counseling notes without disciplinary penalty.<br>JSON: `{ "status": string, "mentor_notes": string }` | `{ "status": "updated", "id": string, "mentor_status": string }` |
| **GET** | `/notifications/all` | Admin | System-wide notification audit log with filters. | `[ { "id": string, "recipient_name": string, "category": string, "delivery_status": string, "retry_count": number } ]` |

---

## 8. Phase 7: Privacy, Image Security & Retention Endpoints

| Method | Path | Target Role | Description / Request Format | Success Response |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/privacy/consent` | All Authenticated | Returns current user's biometric consent record, purpose disclosures, encryption algorithm, and raw image persistence flag (`false`). | `{ "consent_status": "CONSENT_GRANTED", "purpose_limitation": "CAMPUS_IDENTITY_AND_ATTENDANCE_ONLY", "raw_image_persisted": false, "encryption_algorithm": "AES-256-GCM/FERNET" }` |
| **GET** | `/privacy/user/{user_id}/consent` | Faculty / Admin | Queries specific student or staff member's consent posture and purpose classification. | `{ "user_id": string, "consent_status": string, "purpose_limitation": string, "storage_classification": string }` |
| **POST** | `/privacy/consent/grant` | All Authenticated | Grants or renews user biometric consent.<br>JSON: `{ "consent_version": "1.1", "consent": true }` | `{ "status": "success", "consent_status": "CONSENT_GRANTED", "updated_at": string }` |
| **POST** | `/privacy/consent/revoke` | User / Admin | Revokes consent, cryptographically zeroes out face embedding vector in DB, and activates PIN/RFID fallback.<br>JSON: `{ "target_user_id": string, "reason": string }` | `{ "status": "revoked", "consent_status": "CONSENT_REVOKED", "vector_zeroed": true, "fallback_option": string }` |
| **POST** | `/privacy/delete-biometric-data` | User / Admin | "Right to be Forgotten" (GDPR Article 17 / DPDP Section 12). Permanently wipes biometric profile row and issues a verifiable SHA-256 deletion confirmation receipt hash.<br>Query: `?target_user_id={id}` | `{ "status": "permanently_erased", "deletion_receipt_hash": string, "erased_at": string, "regulatory_compliance": [ ... ] }` |
| **GET** | `/privacy/access-logs` | User / Admin | Searchable audit log of every template interaction, verifying accessor, purpose, action, and zero raw-image persistence. | `[ { "accessor_id": string, "target_user_id": string, "purpose": string, "action": string, "status": string, "raw_image_persisted": false } ]` |
| **GET** | `/privacy/retention/status` | Faculty / Admin | Scans database and counts operational records eligible for 90-day data minimization purge. | `{ "retention_policy_days": 90, "cutoff_date": string, "eligible_records": { "total_eligible": number } }` |
| **POST** | `/privacy/retention/run-cleanup` | Admin | Purges ephemeral verification telemetry and delivered notifications older than retention threshold (90 days). Issues signed Retention Compliance Certificate.<br>Query: `?retention_days=90` | `{ "status": "success", "records_purged": { "total_purged": number }, "compliance_certificate": { "hash": string, "standard": string } }` |
| **POST** | `/privacy/backups/create` | Admin | Generates point-in-time database snapshot encrypted with AES-256 and bound to a 30-day lifecycle.<br>Query: `?retention_days=30` | `{ "status": "created", "backup_id": string, "backup_filename": string, "sha256_checksum": string, "expires_at": string }` |
| **GET** | `/privacy/backups` | Admin | Lists all encrypted backups with expiration countdowns and recovery drill audit status. | `[ { "backup_filename": string, "size_bytes": number, "encryption_cipher": string, "is_expired": boolean, "last_recovery_status": string } ]` |
| **POST** | `/privacy/backups/cleanup-expired` | Admin | Scans catalog and securely unlinks/prunes expired backup files from storage. | `{ "status": "success", "pruned_backups_count": number, "reclaimed_bytes": number }` |
| **POST** | `/privacy/backups/test-recovery` | Admin | Executes automated disaster recovery test drill: decrypts backup in isolated scratch SQLite sandbox, executes `PRAGMA integrity_check;`, audits row counts across core entities, and certifies recovery readiness. | `{ "status": "recovery_test_passed", "integrity_check": "ok", "duration_ms": number, "verified_entity_counts": { "users": number, "attendance_records": number, "gate_events": number }, "disaster_recovery_certified": true }` |

---

## 9. Phase 8: Admin Dashboard & Integrity Reports Endpoints

| Method | Path | Target Role | Description / Request Format | Success Response |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/admin/reports/spatial-filters` | Admin | Returns available departments, roles, floors, and rooms for dynamic frontend dropdown filtering. | `{ "departments": string[], "roles": string[], "floors": [ ... ], "rooms": [ ... ] }` |
| **GET** | `/admin/reports/attendance` | Admin | Filterable attendance report by department, floor, room, role, date range, and status. Supports JSON and CSV export formats.<br>Query: `?department={dept}&role={role}&floor_id={fid}&room_id={rid}&date_from={d1}&date_to={d2}&format=json\|csv` | `[ { "id": string, "name": string, "role": string, "department": string, "day": string, "checked_in_at": string, "verification_method": string, "room_name": string, "floor_name": string, "status": string, "event_hash": string } ]` OR CSV file download |
| **GET** | `/admin/reports/gate-access` | Admin | Filterable turnstile gate access report by direction (IN/OUT), event type, gate device, department, and role. Supports JSON and CSV export.<br>Query: `?direction={IN\|OUT}&event_type={type}&gate_id={gid}&format=json\|csv` | `[ { "id": string, "name": string, "role": string, "department": string, "gate_name": string, "direction": string, "event_type": string, "timestamp": string, "synced_offline": bool, "event_hash": string } ]` OR CSV file download |
| **GET** | `/admin/reports/staff-duty` | Admin | Staff duty and shift tracking report cross-referencing assigned work shifts with active check-in compliance status.<br>Query: `?department={dept}&role={role}&shift_status={status}&format=json\|csv` | `[ { "shift_id": string, "name": string, "role": string, "shift_name": string, "start_time": string, "end_time": string, "assigned_location": string, "duty_status": "COMPLETED"\|"PENDING_OR_ABSENT" } ]` OR CSV file download |
| **GET** | `/admin/reports/verification-attempts` | Admin | Security audit telemetry report of all biometric verification attempts with reason codes (`ACCEPT`/`REJECT`), face similarity score, distance, and device ID.<br>Query: `?result={res}&failure_code={code}&format=json\|csv` | `[ { "id": string, "name": string, "role": string, "result": string, "failure_code": string, "face_score": number, "distance_m": number, "created_at": string } ]` OR CSV file download |
| **GET** | `/admin/audit/consolidated-integrity` | Admin | Executes real-time cryptographic verification across all 3 ledgers (Attendance, Gate Access, Room Presence) and anchored Merkle roots. Persists immutable verification record in `audit_verification_logs`. | `{ "audit_id": string, "attendance_chain_valid": bool, "gate_chain_valid": bool, "presence_chain_valid": bool, "overall_tamper_free": bool, "total_records_audited": number, "attendance_count": number, "gate_count": number, "presence_count": number, "tampered_records": [], "verified_at": string }` |
| **GET** | `/admin/audit/history` | Admin | Retrieves chronological historical log of all integrity verification runs with pass/tamper status.<br>Query: `?limit=50` | `[ { "id": string, "verification_type": string, "overall_tamper_free": bool, "total_records_audited": number, "attendance_chain_valid": bool, "gate_chain_valid": bool, "presence_chain_valid": bool, "created_at": string } ]` |
| **POST** | `/admin/audit/merkle-anchor` | Admin | Aggregates daily event hashes from Attendance, Gate, and Presence into a deterministic binary Merkle Tree, calculates Merkle Root $H_{root}$, and commits blockchain anchor receipt.<br>JSON: `{ "day": "YYYY-MM-DD", "network": "ETHEREUM_SEPOLIA_ANCHOR" }` | `{ "id": string, "day": string, "merkle_root": string, "anchor_network": string, "transaction_hash": string, "block_number": number, "event_count": number, "tree_depth": number, "status": "ANCHORED_ON_CHAIN" }` |
| **GET** | `/admin/audit/merkle-anchors` | Admin | Lists recent on-chain Merkle commitments with transaction hashes and block confirmations.<br>Query: `?limit=50` | `[ { "day": string, "merkle_root": string, "anchor_network": string, "transaction_hash": string, "block_number": number, "event_count": number, "status": string } ]` |
| **POST** | `/admin/audit/merkle-proof` | Admin | Generates inclusion proof path ($\lceil \log_2 N \rceil$ sibling hashes and left/right positions) for a given leaf/event hash.<br>JSON: `{ "leaf_hash": string, "commitment_id": string (optional) }` | `{ "found": true, "leaf_hash": string, "merkle_root": string, "proof": [ { "sibling": string, "position": "left"\|"right" } ] }` |
| **POST** | `/admin/audit/verify-merkle-proof` | Admin | Cryptographically hashes leaf hash up through sibling path and asserts equivalence with anchored Merkle root.<br>JSON: `{ "leaf_hash": string, "merkle_root": string, "proof": [ ... ] }` | `{ "verified": true, "leaf_hash": string, "merkle_root": string, "proof_steps": number, "message": string }` |


