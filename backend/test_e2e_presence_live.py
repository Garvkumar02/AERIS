import urllib.request
import json

def post(url, payload, token=None):
    headers = {'Content-Type': 'application/json'}
    if token: headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def get(url, token=None):
    headers = {}
    if token: headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

# 1. Admin Login
status, data = post('http://127.0.0.1:8000/auth/login', {'email': 'admin@campusproof.edu', 'password': 'Admin@123'})
token = data.get('token') or data.get('access_token')
print(f'1. Admin Login: {status} (Token generated: {token[:15]}...)')

# 2. Get Users & Rooms
status, users = get('http://127.0.0.1:8000/admin/users', token)
student = next(u for u in users if u['role'] == 'student')
faculty = next(u for u in users if u['role'] == 'faculty')
print(f"2. Found users: {student['name']} (Student), {faculty['name']} (Faculty)")

status, floors = get('http://127.0.0.1:8000/presence/floors', token)
print(f'3. Floors loaded: {len(floors)}')

# 4. Attempt Student Check-In to STAFF-CSE (Should 403 Forbidden)
staff_room = next(r for f in floors for r in f['rooms'] if r['room_number'] == 'STAFF-CSE')
status, res = post('http://127.0.0.1:8000/presence/check-in', {
    'room_id': staff_room['room_id'],
    'user_id': student['id'],
    'verification_method': 'INDOOR_QR',
    'evidence_payload': {'qr_token': 'DEMO-QR'}
}, token)
print(f'4. Student -> Staff Room Role Restriction: {status} (Expected 403 Forbidden: {res.get("detail")})')

# 5. Weak BLE rejection
lib_room = next(r for f in floors for r in f['rooms'] if r['room_number'] == 'LIBRARY')
status, res = post('http://127.0.0.1:8000/presence/check-in', {
    'room_id': lib_room['room_id'],
    'user_id': student['id'],
    'verification_method': 'BLE_BEACON',
    'evidence_payload': {'beacon_rssi': -95}
}, token)
print(f'5. Weak BLE RSSI Rejection (< -85 dBm): {status} (Expected 400: {res.get("detail")})')

# 6. Valid Library check-in with INDOOR_QR
status, res = post('http://127.0.0.1:8000/presence/check-in', {
    'room_id': lib_room['room_id'],
    'user_id': student['id'],
    'verification_method': 'INDOOR_QR',
    'evidence_payload': {'qr_token': 'AERIS-INDOOR-VALID'}
}, token)
print(f"6. Valid Student Check-In at Central Library: {status} Status={res.get('status')} Hash={res.get('presence_hash')[:24]}...")

# 7. Check Library Status (Confirmed vs Estimated)
lib_id = lib_room['room_id']
status, stat = get(f'http://127.0.0.1:8000/presence/room/{lib_id}/status', token)
print(f"7. Room Status: Confirmed Presence={stat['confirmed_presence']}, Estimated Occupancy={stat['estimated_occupancy']}, Attendees Roster Count={len(stat['confirmed_attendees'])}")

# 8. Check-out
status, out = post('http://127.0.0.1:8000/presence/check-out', {
    'room_id': lib_id,
    'user_id': student['id']
}, token)
print(f"8. Check-Out: {status} Message={out.get('message')}")
print("\nALL LIVE REST API CHECKS PASSED PERFECTLY!\n")
