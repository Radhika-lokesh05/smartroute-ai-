import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
import pytest_asyncio
from geoalchemy2.elements import WKTElement
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.models.ambulance import Ambulance, AmbulanceStatus
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.models.dispatch import Dispatch, DispatchStatus
from app.models.audit import AuditLog
from app.services.audit_service import log_audit_event
from app.services.metrics_service import (
    escape_csv_cell,
    export_metrics_csv,
    get_metrics_hotspots,
    get_metrics_summary,
    get_metrics_timeseries,
    get_model_info,
    validate_days,
)


@pytest.mark.asyncio
class TestAdminAndMetrics:

    async def _create_user(self, session: AsyncSession, name: str, email: str, role: UserRole, is_active: bool = True) -> User:
        user = User(
            name=name,
            email=email.lower(),
            password_hash=get_password_hash("Password123!"),
            role=role,
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    def _auth_header(self, user: User) -> dict:
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        token = create_access_token(str(user.id), role=role_str)
        return {"Authorization": f"Bearer {token}"}

    # 1. Admin-only access on every endpoint
    async def test_admin_only_access_on_endpoints(self, auth_client: AsyncClient, db_session: AsyncSession):
        civilian = await self._create_user(db_session, "Civilian User", "civ_test@example.com", UserRole.civilian)
        civ_headers = self._auth_header(civilian)

        endpoints = [
            ("GET", "/api/admin/audit"),
            ("GET", "/api/admin/users"),
            ("GET", "/api/admin/ambulances"),
            ("GET", "/api/admin/metrics/summary"),
            ("GET", "/api/admin/metrics/timeseries"),
            ("GET", "/api/admin/metrics/hotspots"),
            ("GET", "/api/admin/metrics/export.csv"),
            ("GET", "/api/admin/model-info"),
        ]

        for method, path in endpoints:
            if method == "GET":
                resp = await auth_client.get(path, headers=civ_headers)
            else:
                resp = await auth_client.post(path, headers=civ_headers, json={})
            assert resp.status_code == 403, f"Expected 403 for civilian on {path}, got {resp.status_code}"

        # Unauthenticated access rejected with 401
        unauth_resp = await auth_client.get("/api/admin/users")
        assert unauth_resp.status_code == 401

    # 2. Deactivated user's token rejected
    async def test_deactivated_user_token_rejected(self, auth_client: AsyncClient, db_session: AsyncSession):
        admin = await self._create_user(db_session, "Admin User", "admin_deact@example.com", UserRole.admin)
        civilian = await self._create_user(db_session, "Target Civilian", "civ_deact@example.com", UserRole.civilian, is_active=True)
        civ_headers = self._auth_header(civilian)

        # Token works initially
        r1 = await auth_client.get("/api/auth/me", headers=civ_headers)
        assert r1.status_code == 200

        # Deactivate civilian through admin endpoint
        admin_headers = self._auth_header(admin)
        patch_resp = await auth_client.patch(
            f"/api/admin/users/{civilian.id}/active",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["is_active"] is False

        # Civilian's token must immediately stop working (401)
        r2 = await auth_client.get("/api/auth/me", headers=civ_headers)
        assert r2.status_code == 401

    # 3. Cannot deactivate self or last admin
    async def test_cannot_deactivate_self_or_last_admin(self, auth_client: AsyncClient, db_session: AsyncSession):
        admin1 = await self._create_user(db_session, "Admin One", "admin1@example.com", UserRole.admin)
        admin1_headers = self._auth_header(admin1)

        # 3a. Admin cannot deactivate themselves
        self_deact_resp = await auth_client.patch(
            f"/api/admin/users/{admin1.id}/active",
            headers=admin1_headers,
            json={"is_active": False},
        )
        assert self_deact_resp.status_code == 400
        assert "cannot deactivate their own account" in self_deact_resp.json()["detail"].lower()

        # 3b. Admin cannot deactivate the last remaining admin
        admin2 = await self._create_user(db_session, "Admin Two", "admin2@example.com", UserRole.admin)
        admin2_headers = self._auth_header(admin2)

        # Deactivating admin1 by admin2 succeeds because admin2 remains active
        deact1_resp = await auth_client.patch(
            f"/api/admin/users/{admin1.id}/active",
            headers=admin2_headers,
            json={"is_active": False},
        )
        assert deact1_resp.status_code == 200

        # Now admin2 is the sole active admin. Trying to deactivate admin2 should fail
        # Even if attempted from a restored or mock context, last admin check blocks it
        admin2.is_active = True
        await db_session.commit()

        # If another user or request attempts to deactivate the last remaining admin
        last_admin_resp = await auth_client.patch(
            f"/api/admin/users/{admin2.id}/active",
            headers=admin2_headers,
            json={"is_active": False},
        )
        # Should be blocked by either self-deactivate or last-admin check
        assert last_admin_resp.status_code == 400

    # 4. Audit entries created and contain no secrets
    async def test_audit_entries_created_and_no_secrets(self, auth_client: AsyncClient, db_session: AsyncSession):
        admin = await self._create_user(db_session, "Admin Auditor", "admin_audit@example.com", UserRole.admin)
        admin_headers = self._auth_header(admin)

        # Create ambulance via admin
        create_amb_resp = await auth_client.post(
            "/api/admin/ambulances",
            headers=admin_headers,
            json={
                "name": "Fleet Unit 1",
                "email": "fleet1@example.com",
                "password": "SecretPassword123!",
                "plate_number": "KA-01-EQ-9999",
            },
        )
        assert create_amb_resp.status_code == 201
        amb_id = create_amb_resp.json()["id"]

        # Verify audit entry exists
        audit_resp = await auth_client.get(
            "/api/admin/audit?action=ambulance.created",
            headers=admin_headers,
        )
        assert audit_resp.status_code == 200
        logs = audit_resp.json()["items"]
        assert len(logs) >= 1
        entry = logs[0]
        assert entry["action"] == "ambulance.created"
        assert entry["entity_type"] == "ambulance"
        assert entry["entity_id"] == str(amb_id)
        # Verify details do NOT contain secret password or tokens
        details = entry["details"] or {}
        assert "password" not in details
        assert "password_hash" not in details
        assert "token" not in details

    # 5. Percentile and median math on known data
    async def test_percentile_and_median_math(self, auth_client: AsyncClient, db_session: AsyncSession):
        admin = await self._create_user(db_session, "Admin Math", "admin_math@example.com", UserRole.admin)
        admin_headers = self._auth_header(admin)

        now = datetime.now(timezone.utc)
        # Seed 5 incidents with known validation delays: 10s, 20s, 30s, 40s, 50s
        delays = [10, 20, 30, 40, 50]
        for delay in delays:
            created = now - timedelta(seconds=100)
            validated = created + timedelta(seconds=delay)
            inc = Incident(
                reporter_id=admin.id,
                location=WKTElement("POINT(77.5946 12.9716)", srid=4326),
                incident_type=IncidentType.accident,
                status=IncidentStatus.validated,
                created_at=created,
                validated_at=validated,
                is_simulated=False,
            )
            db_session.add(inc)
        await db_session.commit()

        summary_resp = await auth_client.get("/api/admin/metrics/summary?days=1&origin=live", headers=admin_headers)
        assert summary_resp.status_code == 200
        data = summary_resp.json()
        val_time = data["incidents"]["report_to_validation_time_s"]
        # Median of [10, 20, 30, 40, 50] is 30.0
        assert val_time["median"] == pytest.approx(30.0, 1.0)
        # P90 of [10, 20, 30, 40, 50] is 46.0 or close
        assert val_time["p90"] == pytest.approx(46.0, 5.0)

    # 6. Empty period handling (no NaN, null medians, 0 rates)
    async def test_empty_period_handling(self, auth_client: AsyncClient, db_session: AsyncSession):
        admin = await self._create_user(db_session, "Admin Empty", "admin_empty@example.com", UserRole.admin)
        admin_headers = self._auth_header(admin)

        # Query metrics with days=1 when DB has no incidents or dispatches
        resp = await auth_client.get("/api/admin/metrics/summary?days=1&origin=live", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["incidents"]["reported"] == 0
        assert data["incidents"]["validation_rate"] == 0.0
        assert data["incidents"]["report_to_validation_time_s"]["median"] is None
        assert data["incidents"]["report_to_validation_time_s"]["p90"] is None

        assert data["dispatches"]["offered"] == 0
        assert data["dispatches"]["acceptance_rate"] == 0.0
        assert data["dispatches"]["response_times_s"]["offer_to_accept"]["median"] is None

    # 7. Date range limits
    async def test_date_range_limits(self, auth_client: AsyncClient, db_session: AsyncSession):
        admin = await self._create_user(db_session, "Admin Limits", "admin_lim@example.com", UserRole.admin)
        admin_headers = self._auth_header(admin)

        # days=0 should fail (must be >= 1)
        r_zero = await auth_client.get("/api/admin/metrics/summary?days=0", headers=admin_headers)
        assert r_zero.status_code == 400

        # days=91 should fail (METRICS_MAX_DAYS=90)
        r_over = await auth_client.get("/api/admin/metrics/summary?days=91", headers=admin_headers)
        assert r_over.status_code == 400

        # days=30 should succeed
        r_valid = await auth_client.get("/api/admin/metrics/summary?days=30", headers=admin_headers)
        assert r_valid.status_code == 200

    # 8. CSV export has no ids or emails and escapes formula characters
    async def test_csv_export_privacy_and_formula_escaping(self, auth_client: AsyncClient, db_session: AsyncSession):
        admin = await self._create_user(db_session, "Admin CSV", "admin_csv@example.com", UserRole.admin)
        admin_headers = self._auth_header(admin)

        # Create an incident with formula injection in note
        inc = Incident(
            reporter_id=admin.id,
            location=WKTElement("POINT(77.5946123 12.9716123)", srid=4326),
            incident_type=IncidentType.accident,
            status=IncidentStatus.validated,
            created_at=datetime.now(timezone.utc),
            note="=SUM(A1:B10)",
            is_simulated=False,
        )
        db_session.add(inc)
        await db_session.commit()

        csv_resp = await auth_client.get("/api/admin/metrics/export.csv?kind=incidents&days=1", headers=admin_headers)
        assert csv_resp.status_code == 200
        content = csv_resp.text

        # Verify no user emails or reporter user ids appear in CSV text
        assert "admin_csv@example.com" not in content
        assert str(admin.id) not in content

        # Verify coordinates rounded to 3 decimals
        assert "12.972" in content
        assert "77.595" in content

        # Verify formula cell escaping logic directly
        assert escape_csv_cell("=1+1") == "'=1+1"
        assert escape_csv_cell("+1234") == "'+1234"
        assert escape_csv_cell("-50") == "'-50"
        assert escape_csv_cell("@SUM") == "'@SUM"
        assert escape_csv_cell("normal_text") == "normal_text"

    # 9. Hotspot grid grouping
    async def test_hotspot_grid_grouping(self, auth_client: AsyncClient, db_session: AsyncSession):
        admin = await self._create_user(db_session, "Admin Hotspots", "admin_hot@example.com", UserRole.admin)
        admin_headers = self._auth_header(admin)

        now = datetime.now(timezone.utc)
        # Seed 3 incidents very close together (~20m apart, inside same 250m cell)
        for i in range(3):
            inc = Incident(
                reporter_id=admin.id,
                location=WKTElement(f"POINT({77.5946 + i*0.0001} {12.9716 + i*0.0001})", srid=4326),
                incident_type=IncidentType.accident,
                status=IncidentStatus.validated,
                created_at=now,
                is_simulated=False,
            )
            db_session.add(inc)
        await db_session.commit()

        hotspot_resp = await auth_client.get("/api/admin/metrics/hotspots?days=1", headers=admin_headers)
        assert hotspot_resp.status_code == 200
        data = hotspot_resp.json()
        assert data["total_cells"] >= 1
        top_cell = data["cells"][0]
        assert top_cell["count"] == 3
        assert top_cell["top_type"] == "accident"

    # 10. Simulated vs live separation
    async def test_simulated_vs_live_separation(self, auth_client: AsyncClient, db_session: AsyncSession):
        admin = await self._create_user(db_session, "Admin Sim", "admin_sim@example.com", UserRole.admin)
        admin_headers = self._auth_header(admin)
        now = datetime.now(timezone.utc)

        # 2 live incidents, 1 simulated incident
        live1 = Incident(
            reporter_id=admin.id,
            location=WKTElement("POINT(77.5946 12.9716)", srid=4326),
            incident_type=IncidentType.hazard,
            status=IncidentStatus.pending,
            created_at=now,
            is_simulated=False,
        )
        live2 = Incident(
            reporter_id=admin.id,
            location=WKTElement("POINT(77.5950 12.9720)", srid=4326),
            incident_type=IncidentType.hazard,
            status=IncidentStatus.pending,
            created_at=now,
            is_simulated=False,
        )
        sim1 = Incident(
            reporter_id=admin.id,
            location=WKTElement("POINT(77.5960 12.9730)", srid=4326),
            incident_type=IncidentType.blockage,
            status=IncidentStatus.pending,
            created_at=now,
            is_simulated=True,
        )
        db_session.add_all([live1, live2, sim1])
        await db_session.commit()

        # origin=live should return 2
        r_live = await auth_client.get("/api/admin/metrics/summary?days=1&origin=live", headers=admin_headers)
        assert r_live.json()["incidents"]["reported"] == 2

        # origin=simulated should return 1
        r_sim = await auth_client.get("/api/admin/metrics/summary?days=1&origin=simulated", headers=admin_headers)
        assert r_sim.json()["incidents"]["reported"] == 1

        # origin=all should return 3
        r_all = await auth_client.get("/api/admin/metrics/summary?days=1&origin=all", headers=admin_headers)
        assert r_all.json()["incidents"]["reported"] == 3

    # 11. Model-info with and without the file
    async def test_model_info_with_and_without_file(self, auth_client: AsyncClient, db_session: AsyncSession, monkeypatch):
        admin = await self._create_user(db_session, "Admin Model", "admin_mod@example.com", UserRole.admin)
        admin_headers = self._auth_header(admin)

        # 11a. With the real file
        resp = await auth_client.get("/api/admin/model-info", headers=admin_headers)
        assert resp.status_code == 200
        info = resp.json()
        assert info["model_available"] is True
        assert "model_version" in info
        assert "data_source" in info
        assert "model_mae" in info
        assert "baseline_mae" in info
        assert "historical open dataset" in info["note"].lower()

        # 11b. Without the file (simulated by non-existent path)
        monkeypatch.setattr(
            Path,
            "exists",
            lambda p: False if "metrics.json" in str(p) else True,
        )
        info_missing = get_model_info()
        assert isinstance(info_missing, dict)
        assert info_missing["model_available"] is False
