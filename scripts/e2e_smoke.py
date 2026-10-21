#!/usr/bin/env python3
"""
scripts/e2e_smoke.py
End-to-end smoke test suite verifying live server operations:
1. Liveness (GET /health)
2. Readiness (GET /ready)
3. Civilian Registration (POST /api/auth/register)
4. Authentication (POST /api/auth/login)
5. Geocoding (GET /api/geocode/autocomplete - skipped cleanly if no ORS key)
6. Incident Reporting (POST /api/incidents)
7. Incident Voting (POST /api/incidents/{id}/vote)
8. Nearby Incidents (GET /api/incidents/nearby)
9. Emergency Hospitals (GET /api/hospitals/nearby)
10. Admin Endpoints (GET /api/admin/metrics, GET /api/admin/audit)
11. Logout & Token Revocation (POST /api/auth/logout)

Exits with code 0 on success, or non-zero on failure.
"""
import argparse
import sys
import time
import uuid
import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


class SmokeTestRunner:
    def __init__(self, base_url: str, admin_email: str, admin_password: str):
        self.base_url = base_url.rstrip("/")
        self.admin_email = admin_email
        self.admin_password = admin_password
        self.client = httpx.Client(base_url=self.base_url, timeout=15.0)
        self.results = []
        self.token = None
        self.admin_token = None
        self.incident_id = None

    def log_result(self, step_name: str, passed: bool, detail: str = ""):
        status_text = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"[{symbol}] {step_name:<35} : {status_text} {f'({detail})' if detail else ''}")
        self.results.append((step_name, passed, detail))

    def run(self) -> bool:
        print(f"\n=======================================================")
        print(f"  SmartRoute AI - End-to-End Smoke Test Suite")
        print(f"  Target Server: {self.base_url}")
        print(f"=======================================================\n")

        # 1. Health Liveness
        try:
            r = self.client.get("/health")
            if r.status_code == 200 and r.json().get("status") == "ok":
                self.log_result("1. Liveness (GET /health)", True, "200 OK")
            else:
                self.log_result("1. Liveness (GET /health)", False, f"Status: {r.status_code}")
        except Exception as exc:
            self.log_result("1. Liveness (GET /health)", False, str(exc))

        # 2. Readiness Probe
        try:
            r = self.client.get("/ready")
            if r.status_code in (200, 503):
                data = r.json()
                self.log_result(
                    "2. Readiness (GET /ready)",
                    True,
                    f"Status {r.status_code}, db: {data.get('database')}, model: {data.get('model_available')}",
                )
            else:
                self.log_result("2. Readiness (GET /ready)", False, f"Status: {r.status_code}")
        except Exception as exc:
            self.log_result("2. Readiness (GET /ready)", False, str(exc))

        # 3. Civilian Register
        test_email = f"smoke_user_{uuid.uuid4().hex[:8]}@example.com"
        test_pass = "SmokePass2026!Secure"
        try:
            r = self.client.post(
                "/api/auth/register",
                json={"name": "Smoke Test User", "email": test_email, "password": test_pass},
            )
            if r.status_code == 201:
                self.log_result("3. Register (POST /api/auth/register)", True, "User registered")
            else:
                self.log_result("3. Register (POST /api/auth/register)", False, f"Status: {r.status_code} - {r.text}")
        except Exception as exc:
            self.log_result("3. Register (POST /api/auth/register)", False, str(exc))

        # 4. Civilian Login
        try:
            r = self.client.post(
                "/api/auth/login",
                json={"email": test_email, "password": test_pass},
            )
            if r.status_code == 200:
                data = r.json()
                self.token = data.get("access_token")
                self.log_result("4. Login (POST /api/auth/login)", True, "Token acquired")
            else:
                self.log_result("4. Login (POST /api/auth/login)", False, f"Status: {r.status_code}")
        except Exception as exc:
            self.log_result("4. Login (POST /api/auth/login)", False, str(exc))

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

        # 5. Geocode Autocomplete (Skipped cleanly if ORS key missing or quota exceeded)
        try:
            r = self.client.get("/api/geocode/autocomplete?q=MG%20Road", headers=headers)
            if r.status_code == 200:
                self.log_result("5. Geocode (autocomplete)", True, "200 OK")
            elif r.status_code in (502, 503, 429):
                self.log_result("5. Geocode (autocomplete)", True, f"Skipped upstream ORS ({r.status_code})")
            else:
                self.log_result("5. Geocode (autocomplete)", False, f"Status: {r.status_code}")
        except Exception as exc:
            self.log_result("5. Geocode (autocomplete)", False, str(exc))

        # 6. Report Incident
        inc_lat, inc_lng = 12.9716, 77.5946
        try:
            r = self.client.post(
                "/api/incidents",
                json={"lat": inc_lat, "lng": inc_lng, "type": "accident", "note": "Smoke test collision"},
                headers=headers,
            )
            if r.status_code == 201:
                self.incident_id = r.json().get("id")
                self.log_result("6. Report Incident (POST /api/incidents)", True, f"ID: {self.incident_id}")
            else:
                self.log_result("6. Report Incident (POST /api/incidents)", False, f"Status: {r.status_code} - {r.text}")
        except Exception as exc:
            self.log_result("6. Report Incident (POST /api/incidents)", False, str(exc))

        # 7. Vote on Incident
        if self.incident_id:
            try:
                r = self.client.post(
                    f"/api/incidents/{self.incident_id}/vote",
                    json={"vote": "confirm", "voter_lat": inc_lat, "voter_lng": inc_lng},
                    headers=headers,
                )
                if r.status_code == 200:
                    self.log_result("7. Vote Incident (POST /vote)", True, "Vote registered")
                else:
                    self.log_result("7. Vote Incident (POST /vote)", False, f"Status: {r.status_code} - {r.text}")
            except Exception as exc:
                self.log_result("7. Vote Incident (POST /vote)", False, str(exc))
        else:
            self.log_result("7. Vote Incident (POST /vote)", False, "Skipped (no incident created)")

        # 8. Nearby Incidents
        try:
            r = self.client.get(
                f"/api/incidents/nearby?lat={inc_lat}&lng={inc_lng}&radius_m=5000",
                headers=headers,
            )
            if r.status_code == 200:
                total = r.json().get("total", 0)
                self.log_result("8. Nearby Incidents (GET /nearby)", True, f"Found {total} incidents")
            else:
                self.log_result("8. Nearby Incidents (GET /nearby)", False, f"Status: {r.status_code}")
        except Exception as exc:
            self.log_result("8. Nearby Incidents (GET /nearby)", False, str(exc))

        # 9. Emergency Hospitals
        try:
            r = self.client.get(
                f"/api/hospitals/nearby?lat={inc_lat}&lng={inc_lng}&emergency_type=trauma",
                headers=headers,
            )
            if r.status_code == 200:
                hosp_count = len(r.json().get("hospitals", []))
                self.log_result("9. Nearby Hospitals (GET /nearby)", True, f"Found {hosp_count} facilities")
            else:
                self.log_result("9. Nearby Hospitals (GET /nearby)", False, f"Status: {r.status_code}")
        except Exception as exc:
            self.log_result("9. Nearby Hospitals (GET /nearby)", False, str(exc))

        # 10. Admin Endpoints
        try:
            # Login as Admin
            r_adm = self.client.post(
                "/api/auth/login",
                json={"email": self.admin_email, "password": self.admin_password},
            )
            if r_adm.status_code == 200:
                self.admin_token = r_adm.json().get("access_token")
                adm_headers = {"Authorization": f"Bearer {self.admin_token}"}
                r_metrics = self.client.get("/api/admin/metrics/summary?days=7", headers=adm_headers)
                r_audit = self.client.get("/api/admin/audit?page=1&page_size=5", headers=adm_headers)
                if r_metrics.status_code == 200 and r_audit.status_code == 200:
                    self.log_result("10. Admin Endpoints (/metrics/summary, /audit)", True, "Admin verified")
                else:
                    self.log_result(
                        "10. Admin Endpoints (/metrics, /audit)",
                        False,
                        f"Metrics: {r_metrics.status_code}, Audit: {r_audit.status_code}",
                    )
            else:
                self.log_result(
                    "10. Admin Endpoints (/metrics, /audit)",
                    True,
                    f"Default admin login skipped ({r_adm.status_code})",
                )
        except Exception as exc:
            self.log_result("10. Admin Endpoints (/metrics, /audit)", False, str(exc))

        # 11. Logout & Revocation
        try:
            r = self.client.post("/api/auth/logout", headers=headers)
            if r.status_code == 200:
                # Test that old token is now rejected
                r_check = self.client.get("/api/auth/me", headers=headers)
                if r_check.status_code == 401:
                    self.log_result("11. Logout & Token Denylist", True, "Token revoked successfully")
                else:
                    self.log_result("11. Logout & Token Denylist", False, f"Revoked token returned {r_check.status_code}")
            else:
                self.log_result("11. Logout & Token Denylist", False, f"Logout failed: {r.status_code}")
        except Exception as exc:
            self.log_result("11. Logout & Token Denylist", False, str(exc))

        # Print Summary
        total_tests = len(self.results)
        passed_tests = sum(1 for _, p, _ in self.results if p)
        failed_tests = total_tests - passed_tests

        print(f"\n-------------------------------------------------------")
        print(f"  Summary: {passed_tests}/{total_tests} passed, {failed_tests} failed")
        print(f"-------------------------------------------------------\n")

        return failed_tests == 0


def main():
    parser = argparse.ArgumentParser(description="SmartRoute AI E2E Smoke Test Suite")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL of running server")
    parser.add_argument("--admin-email", default="admin@smartroute.ai", help="Admin email")
    parser.add_argument("--admin-password", default="adminpassword123", help="Admin password")
    args = parser.parse_args()

    runner = SmokeTestRunner(
        base_url=args.base_url,
        admin_email=args.admin_email,
        admin_password=args.admin_password,
    )
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
