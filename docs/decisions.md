# CampusProof - Architectural Decisions & Changelog

### AD-01: Liveness Detection Approach
- **Decision**: Server-directed randomized challenge (`TURN_LEFT` / `TURN_RIGHT`) comparing head pose yaw delta (>= 15 degrees) between neutral and challenge frames.
- **Rationale**: Completely prevents static photo presentation, photo replays, and single frame spoofing without requiring client-side heavy neural models or battery drain on low-end devices.

### AD-02: Device Binding Policy
- **Decision**: Automatic registration of the first device (`device_id`) used during valid attendance verification. Subsequent attempts with a different `device_id` result in `DEVICE_NOT_REGISTERED`.
- **Rationale**: Eliminates proxy check-in by peers without manual admin intervention during registration onboarding.

### AD-03: Geofence & Location Spoof Defense
- **Decision**: Server-side Haversine distance computation against active campus coordinates + Android `is_mock` boolean flag check + GPS accuracy threshold gate (`MAX_GPS_ACCURACY_M = 100m`).
- **Rationale**: Client can never decide attendance validity; mock GPS applications are immediately flagged and rejected.

### AD-04: Biometric Privacy & Security
- **Decision**: No raw face images are stored on server disk or database. Only L2-normalized 512-d ArcFace embeddings encrypted with Fernet symmetric cryptography (`FERNET_KEY`) are stored. Revocation zeroes out and deletes records.
