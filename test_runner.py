import sqlite3
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8001"

def req(method, path, body=None, token=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()) if e.read() else None

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# DB check
section("DB SCHEMA CHECK")
conn = sqlite3.connect("clinic.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print(f"Tables: {tables}")
for t in tables:
    c.execute(f"PRAGMA table_info({t})")
    cols = c.fetchall()
    print(f"\n{t}:")
    for col in cols:
        print(f"  {col}")
conn.close()

# Start server
section("API ENDPOINT TESTS")

# 1. Login as admin
section("Login as admin")
code, resp = req("POST", "/auth/login", {"username": "admin", "password": "clinic123"})
print(f"Status: {code}, Response: {json.dumps(resp, indent=2)[:200]}")
admin_token = resp.get("access_token") if code == 200 else None

# 2. Get users list
section("Get all users (admin)")
if admin_token:
    code, resp = req("GET", "/users", token=admin_token)
    print(f"Status: {code}")
    if code == 200 and resp:
        for u in resp[:3]:
            print(f"  {u}")

# 3. Check /uploads is protected
section("Check /uploads static removed")
try:
    r = urllib.request.urlopen(f"{BASE}/uploads")
    print(f"WARNING: /uploads still accessible! Status: {r.status}")
except urllib.error.HTTPError as e:
    print(f"/uploads returns {e.code} (expected 404 if removed)")
except Exception as e:
    print(f"/uploads error: {e} (expected if removed)")

# 4. Test patient self-booking (POST /appointments/my)
section("Patient self-booking")
if admin_token:
    # First find a patient user
    code, users = req("GET", "/users", token=admin_token)
    patients = [u for u in users if u.get("role") == "patient"] if code == 200 else []
    doctors = [u for u in users if u.get("role") == "doctor"] if code == 200 else []
    if patients and doctors:
        patient = patients[0]
        doctor = doctors[0]
        doctor_token = None

        # Login as patient
        code2, pat_resp = req("POST", "/auth/login", {"username": patient["username"], "password": "clinic123"})
        if code2 == 200:
            patient_token = pat_resp["access_token"]
            print(f"Patient token: {patient_token[:20]}...")

            # Try patient self-booking
            book_data = {
                "doctor_id": doctor["id"],
                "patient_id": patient["id"],
                "appointment_date": "2026-08-01",
                "appointment_time": "10:00",
                "reason": "Test booking"
            }
            code3, book_resp = req("POST", "/appointments/my", body=book_data, token=patient_token)
            print(f"Patient booking status: {code3}, Response: {json.dumps(book_resp, indent=2)[:300]}")

# 5. Test doctor status update
section("Doctor status update")
if admin_token:
    code, doctors = req("GET", "/users", token=admin_token)
    doctors_list = [u for u in doctors if u.get("role") == "doctor"] if code == 200 else []
    if doctors_list:
        doc = doctors_list[0]
        code2, doc_resp = req("POST", "/auth/login", {"username": doc["username"], "password": "clinic123"})
        if code2 == 200:
            doc_token = doc_resp["access_token"]
            # Try updating status
            update_data = {"status": "available", "current_patient_id": None}
            code3, upd_resp = req("PUT", "/appointments/1/status", body=update_data, token=doc_token)
            print(f"Doctor status update status: {code3}, Response: {json.dumps(upd_resp, indent=2)[:300]}")

# 6. Test video join requires auth
section("Video join auth check")
# Try without token
code, resp = req("POST", "/appointments/1/join/patient", body={"appointment_id": 1})
print(f"Unauthenticated join/patient: {code}")
# Try with token
if admin_token:
    code2, resp2 = req("POST", "/appointments/1/join/patient", body={"appointment_id": 1}, token=admin_token)
    print(f"Admin join/patient (should fail - not a patient): {code2}")

# 7. Test report download
section("Report download auth check")
code, resp = req("GET", "/emr/reports/1/download")
print(f"Unauthenticated report download: {code}")
if admin_token:
    code2, resp2 = req("GET", "/emr/reports/1/download", token=admin_token)
    print(f"Authenticated report download: {code2}")

# 8. Test get my appointments
section("Get my appointments")
if admin_token:
    code, users = req("GET", "/users", token=admin_token)
    patients = [u for u in users if u.get("role") == "patient"] if code == 200 else []
    if patients:
        pat = patients[0]
        code2, pat_resp = req("POST", "/auth/login", {"username": pat["username"], "password": "clinic123"})
        if code2 == 200:
            pat_token = pat_resp["access_token"]
            code3, myappts = req("GET", "/appointments/my", token=pat_token)
            print(f"Patient's appointments: {code3}, count: {len(myappts) if code3 == 200 else 'N/A'}")

print("\n\n=== TEST RUN COMPLETE ===")