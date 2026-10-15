"""
Automated End-to-End Verification Test Suite for AERIS CampusProof Backend.
Tests all security gates, geofencing, biometric enrollment, and anti-spoofing rules.
"""
import io
import cv2
import numpy as np
import requests

BASE_URL = "http://127.0.0.1:8000"

def create_synthetic_face_image(yaw_offset: int = 0, blur: bool = False) -> bytes:
    """Generates a synthetic face image with controllable eye positioning and blur."""
    img = np.ones((250, 250, 3), dtype=np.uint8) * 220
    
    # Face oval
    cv2.ellipse(img, (125, 125), (75, 95), 0, 0, 360, (180, 150, 130), -1)
    
    # Eyes (simulating head pose yaw via horizontal displacement)
    left_eye_x = 95 + yaw_offset
    right_eye_x = 155 + yaw_offset
    cv2.circle(img, (left_eye_x, 110), 8, (40, 40, 40), -1)
    cv2.circle(img, (right_eye_x, 110), 8, (40, 40, 40), -1)
    
    # Nose
    cv2.line(img, (125 + yaw_offset // 2, 115), (125 + yaw_offset // 2, 145), (100, 80, 70), 3)
    
    # Mouth
    cv2.ellipse(img, (125 + yaw_offset // 2, 175), (25, 12), 0, 0, 180, (80, 50, 50), -1)
    
    if blur:
        img = cv2.GaussianBlur(img, (25, 25), 0)

    _, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()

def run_tests():
    print("=== 1. Testing Server Root Endpoint ===")
    r = requests.get(f"{BASE_URL}/")
    assert r.status_code == 200, f"Root failed: {r.text}"
    print(f" Root OK: {r.json()['project']}")

    print("\n=== 2. Testing Authentication (Staff & Admin) ===")
    # Staff login
    r_staff = requests.post(f"{BASE_URL}/auth/login", json={"email": "priya.verma@campusproof.edu", "password": "Staff@123"})
    assert r_staff.status_code == 200, f"Staff login failed: {r_staff.text}"
    staff_token = r_staff.json()["token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    print(f" Staff Login OK: {r_staff.json()['name']} ({r_staff.json()['employee_id']})")

    # Admin login
    r_admin = requests.post(f"{BASE_URL}/auth/login", json={"email": "admin@campusproof.edu", "password": "Admin@123"})
    assert r_admin.status_code == 200, f"Admin login failed: {r_admin.text}"
    admin_token = r_admin.json()["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print(f" Admin Login OK: {r_admin.json()['name']}")

    print("\n=== 3. Testing Device Registration ===")
    r_dev = requests.post(
        f"{BASE_URL}/devices/register",
        json={"device_id": "test-device-pixel-8", "platform": "android"},
        headers=staff_headers
    )
    assert r_dev.status_code == 200, f"Device registration failed: {r_dev.text}"
    print(" Device Register OK")

    print("\n=== 4. Testing Biometric Enrollment ===")
    front_bytes = create_synthetic_face_image(yaw_offset=0)
    left_bytes = create_synthetic_face_image(yaw_offset=-20)
    right_bytes = create_synthetic_face_image(yaw_offset=20)

    files = {
        "front": ("front.jpg", front_bytes, "image/jpeg"),
        "left": ("left.jpg", left_bytes, "image/jpeg"),
        "right": ("right.jpg", right_bytes, "image/jpeg")
    }
    data = {"consent": "true"}
    r_enroll = requests.post(f"{BASE_URL}/biometric/enroll", data=data, files=files, headers=staff_headers)
    assert r_enroll.status_code == 200, f"Enrollment failed: {r_enroll.text}"
    print(f" Enrollment OK: {r_enroll.json()}")

    print("\n=== 5. Testing Attendance Session Challenge ===")
    r_sess = requests.post(f"{BASE_URL}/attendance/session", headers=staff_headers)
    assert r_sess.status_code == 200, f"Session create failed: {r_sess.text}"
    sess_data = r_sess.json()
    session_id = sess_data["session_id"]
    challenge = sess_data["challenge"]
    print(f" Session OK: ID={session_id}, Challenge={challenge}")

    print("\n=== 6. Testing Security Gate: Mock GPS Defense ===")
    mock_files = {
        "frame_neutral": ("neutral.jpg", front_bytes, "image/jpeg"),
        "frame_challenge": ("challenge.jpg", left_bytes if challenge == "TURN_LEFT" else right_bytes, "image/jpeg")
    }
    mock_payload = {
        "session_id": session_id,
        "lat": 26.8228,
        "lng": 75.8648,
        "accuracy": 15.0,
        "is_mock": "true",
        "device_id": "test-device-pixel-8"
    }
    r_mock = requests.post(f"{BASE_URL}/attendance/verify", data=mock_payload, files=mock_files, headers=staff_headers)
    assert r_mock.json()["code"] == "MOCK_LOCATION", f"Mock check failed: {r_mock.json()}"
    print(" Mock Location Blocked: PASS (MOCK_LOCATION)")

    print("\n=== 7. Testing Security Gate: Geofence Outside Campus ===")
    # New session
    r_sess = requests.post(f"{BASE_URL}/attendance/session", headers=staff_headers)
    session_id = r_sess.json()["session_id"]
    challenge = r_sess.json()["challenge"]

    outside_payload = {
        "session_id": session_id,
        "lat": 28.7041,  # Delhi coordinate (far from Jaipur campus)
        "lng": 77.1025,
        "accuracy": 10.0,
        "is_mock": "false",
        "device_id": "test-device-pixel-8"
    }
    files = {
        "frame_neutral": ("neutral.jpg", front_bytes, "image/jpeg"),
        "frame_challenge": ("challenge.jpg", left_bytes if challenge == "TURN_LEFT" else right_bytes, "image/jpeg")
    }
    r_outside = requests.post(f"{BASE_URL}/attendance/verify", data=outside_payload, files=files, headers=staff_headers)
    assert r_outside.json()["code"] == "OUTSIDE_CAMPUS", f"Outside geofence check failed: {r_outside.json()}"
    print(" Outside Campus Blocked: PASS (OUTSIDE_CAMPUS)")

    print("\n=== 8. Testing Valid Attendance Verification ===")
    r_sess = requests.post(f"{BASE_URL}/attendance/session", headers=staff_headers)
    session_id = r_sess.json()["session_id"]
    challenge = r_sess.json()["challenge"]

    valid_payload = {
        "session_id": session_id,
        "lat": 26.8228,  # Exact campus coordinate
        "lng": 75.8648,
        "accuracy": 12.0,
        "is_mock": "false",
        "device_id": "test-device-pixel-8"
    }
    target_challenge_frame = left_bytes if challenge == "TURN_LEFT" else right_bytes
    files = {
        "frame_neutral": ("neutral.jpg", front_bytes, "image/jpeg"),
        "frame_challenge": ("challenge.jpg", target_challenge_frame, "image/jpeg")
    }
    r_valid = requests.post(f"{BASE_URL}/attendance/verify", data=valid_payload, files=files, headers=staff_headers)
    print(f" Valid Verification Result: {r_valid.json()}")
    assert r_valid.json()["result"] == "ACCEPT", f"Valid verification failed: {r_valid.json()}"
    print(" Valid Check-in Accepted: PASS (ACCEPT)")

    print("\n=== 9. Testing Duplicate Check-in Guard ===")
    r_sess = requests.post(f"{BASE_URL}/attendance/session", headers=staff_headers)
    session_id = r_sess.json()["session_id"]
    valid_payload["session_id"] = session_id
    files = {
        "frame_neutral": ("neutral.jpg", front_bytes, "image/jpeg"),
        "frame_challenge": ("challenge.jpg", target_challenge_frame, "image/jpeg")
    }
    r_dup = requests.post(f"{BASE_URL}/attendance/verify", data=valid_payload, files=files, headers=staff_headers)
    assert r_dup.json()["result"] == "ALREADY_MARKED", f"Duplicate check failed: {r_dup.json()}"
    print(" Duplicate Check-in Prevented: PASS (ALREADY_MARKED)")

    print("\n=== 10. Testing Admin Stats & Attendance Dashboard API ===")
    r_stats = requests.get(f"{BASE_URL}/admin/stats", headers=admin_headers)
    assert r_stats.status_code == 200, f"Admin stats failed: {r_stats.text}"
    print(f" Admin Stats OK: Present={r_stats.json()['present_today']}, Total Staff={r_stats.json()['total_staff']}")

    r_daily = requests.get(f"{BASE_URL}/admin/attendance", headers=admin_headers)
    assert r_daily.status_code == 200, f"Admin attendance failed: {r_daily.text}"
    print(f" Admin Daily Attendance OK: Present Count={len(r_daily.json()['present'])}, Absent Count={len(r_daily.json()['absent'])}")

    print("\n ALL VERIFICATION AND SECURITY GATES PASSED SUCCESSFULLY! ")

if __name__ == "__main__":
    run_tests()
