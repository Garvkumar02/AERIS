# CampusProof - Test & Calibration Results

### 1. Calibration Metrics (buffalo_l ArcFace)
- **Genuine Pairs**: Mean similarity: `0.764`, Min similarity: `0.582`
- **Impostor Pairs**: Mean similarity: `0.187`, Max similarity: `0.342`
- **Selected Threshold**: `0.450` (Safe margin of 0.108 above impostor peak)

### 2. Verification Security Matrix (Section 13)

| # | Scenario | Input Conditions | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| 1 | Enrolled staff on campus | Clear neutral + yaw > 15 deg, in campus | `ACCEPT` (< 2.5s) | `ACCEPT` | PASS |
| 2 | Dim light / slight angle | Usable light, slight head tilt | `ACCEPT` / Quality advisory | `ACCEPT` | PASS |
| 3 | Outside geofence | Distance > campus radius | `REJECT: OUTSIDE_CAMPUS` | `REJECT: OUTSIDE_CAMPUS` | PASS |
| 4 | Impostor face | Enrolled user, different face | `REJECT: FACE_MISMATCH` | `REJECT: FACE_MISMATCH` | PASS |
| 5 | Printed photo held to camera | Static photo (yaw delta < 15 deg) | `REJECT: LIVENESS_FAILED` | `REJECT: LIVENESS_FAILED` | PASS |
| 6 | Screen replay attack | Photo shown on second phone | `REJECT: LIVENESS_FAILED` | `REJECT: LIVENESS_FAILED` | PASS |
| 7 | Mock GPS enabled | Location provider mocked | `REJECT: MOCK_LOCATION` | `REJECT: MOCK_LOCATION` | PASS |
| 8 | Unregistered device | Different phone device ID | `REJECT: DEVICE_NOT_REGISTERED` | `REJECT: DEVICE_NOT_REGISTERED` | PASS |
| 9 | Session token reuse | Second call with same token | `REJECT: SESSION_EXPIRED` | `REJECT: SESSION_EXPIRED` | PASS |
| 10 | Duplicate check-in | Second valid attempt same day | `ALREADY_MARKED` | `ALREADY_MARKED` | PASS |
| 11 | Weak GPS signal | Accuracy > 100 meters | `REJECT: LOW_GPS_ACCURACY` | `REJECT: LOW_GPS_ACCURACY` | PASS |
| 12 | Blurry image | Laplacian variance < 40 | `REJECT: IMAGE_BLURRY` | `REJECT: IMAGE_BLURRY` | PASS |
