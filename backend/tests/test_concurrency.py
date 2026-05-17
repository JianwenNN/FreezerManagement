import threading
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.database import get_db, SessionLocal


def make_client():
    """
    Create an isolated database session and test client for each thread.
    Threads must not share sessions — SQLAlchemy sessions are not thread-safe.
    """
    session = SessionLocal()

    def override():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override
    client = TestClient(app, raise_server_exceptions=False)
    return client, session


# ── Test 1: Concurrent suggests do not oversell capacity ─────────────────────

def test_concurrent_suggest_no_oversell(freezer):
    """
    Scenario:
        The freezer has 8 drawers, each holding 5 study sample containers
        (total capacity = 40). Ten threads simultaneously request an
        allocation of 5 containers each (50 total requested).

    Expected:
        The sum of all successfully allocated containers must not exceed
        the physical capacity of the freezer. available_space_in_drawer()
        subtracts active reservations, so concurrent suggest calls that
        race through the TOCTOU window may both succeed, but the combined
        allocation must still respect the hard ceiling enforced at confirm time.

    What this validates:
        The reservation pattern limits over-allocation at the suggest stage.
        Any residual over-allocation is caught by the advisory lock and DB
        trigger at the confirm stage.
    """
    results = []
    errors  = []

    def suggest():
        client, session = make_client()
        try:
            resp = client.post("/api/v1/containers/allocate-proximity/", json={
                "number_of_containers": 5,
                "sample_type":          "study_sample_container",
                "freezer_asset_id":     "TEST-FRZ-01",
            })
            results.append(resp)
        except Exception as e:
            errors.append(e)
        finally:
            session.close()

    threads = [threading.Thread(target=suggest) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()

    successful = [r for r in results if r.status_code == 200]
    failed     = [r for r in results if r.status_code != 200]

    total_allocated = sum(
        sum(a["container_count"] for a in r.json())
        for r in successful
    )

    total_capacity = (
        freezer["num_of_layers"]
        * freezer["num_of_rack_per_layer"]
        * freezer["num_of_drawer_per_rack"]
        * freezer["study_sample_capacity"]
    )

    print(f"\nSuccessful suggests: {len(successful)}, failed: {len(failed)}")
    print(f"Total allocated: {total_allocated}, total capacity: {total_capacity}")

    assert not errors, f"Unexpected exceptions during suggest: {errors}"
    assert total_allocated <= total_capacity, (
        f"Oversold: allocated {total_allocated} but capacity is only {total_capacity}"
    )


# ── Test 2: Concurrent confirms on the same drawer — only one succeeds ────────

def test_concurrent_confirm_same_drawer(freezer):
    """
    Scenario:
        Two users each run a suggest and receive a reservation token for the
        same drawer. They then submit their confirm requests simultaneously.

    Expected:
        The advisory lock (pg_advisory_xact_lock) serialises the two
        transactions. The second transaction re-checks capacity after the
        first commits and finds no remaining space, returning 409.
        At most one confirm can succeed.

    What this validates:
        The advisory lock is the hard concurrency guarantee at the confirm
        stage. Even if both reservations passed the suggest-stage capacity
        check, only one commit lands in the database.
    """
    client1, s1 = make_client()
    client2, s2 = make_client()

    # Both users receive a reservation for the same freezer
    r1 = client1.post("/api/v1/containers/allocate-proximity/", json={
        "number_of_containers": 4,
        "sample_type":          "study_sample_container",
        "freezer_asset_id":     "TEST-FRZ-01",
    }).json()

    r2 = client2.post("/api/v1/containers/allocate-proximity/", json={
        "number_of_containers": 4,
        "sample_type":          "study_sample_container",
        "freezer_asset_id":     "TEST-FRZ-01",
    }).json()

    assert r1, "First suggest should succeed"
    assert r2, "Second suggest should succeed"

    confirm_results = []

    def confirm(client, allocation, barcode_prefix):
        drawers = [
            {
                "drawer_id":  a["drawer_id"],
                "containers": [
                    {
                        "container_barcode": f"{barcode_prefix}-{i}",
                        "study_name":        "CONCURRENT-TEST",
                    }
                    for i in range(a["container_count"])
                ],
            }
            for a in allocation
        ]
        tokens = [a["reservation_token"] for a in allocation]

        resp = client.post("/api/v1/containers/confirm/study-sample/", json={
            "freezer_asset_id":     "TEST-FRZ-01",
            "originally_requested": 4,
            "reservation_tokens":   tokens,
            "drawers":              drawers,
            "partial_allowed":      True,
        })
        confirm_results.append(resp.status_code)

    t1 = threading.Thread(target=confirm, args=(client1, r1, "BC-A"))
    t2 = threading.Thread(target=confirm, args=(client2, r2, "BC-B"))

    # Fire simultaneously
    t1.start(); t2.start()
    t1.join();  t2.join()
    s1.close(); s2.close()

    print(f"\nConfirm status codes: {confirm_results}")

    success_count = confirm_results.count(200)
    assert success_count <= 1, (
        f"Both confirms succeeded — the advisory lock is not working. "
        f"Status codes: {confirm_results}"
    )


# ── Test 3: Expired reservations release space ────────────────────────────────

def test_expired_reservation_frees_space(freezer, db):
    """
    Scenario:
        A user suggests an allocation that occupies all remaining space in a
        drawer. The reservation is then artificially expired (simulating what
        the background scheduler does every minute). A second suggest is
        issued for the same space.

    Expected:
        available_space_in_drawer() filters reservations by expires_at > NOW(),
        so an expired reservation is invisible to the capacity calculation.
        The second suggest sees the full capacity and succeeds.

    What this validates:
        The system is self-healing. Abandoned allocations — user closed the
        browser, session timed out, network dropped — do not permanently lock
        drawer space. No manual intervention is required once the TTL expires.
    """
    client, session = make_client()

    # Occupy the drawer with a reservation
    resp = client.post("/api/v1/containers/allocate-proximity/", json={
        "number_of_containers": 5,
        "sample_type":          "study_sample_container",
        "freezer_asset_id":     "TEST-FRZ-01",
    })
    assert resp.status_code == 200
    allocation = resp.json()
    drawer_id  = allocation[0]["drawer_id"]

    # Artificially expire the reservation (simulates the APScheduler cleanup job)
    db.execute(text("""
        UPDATE drawer_reservation
        SET expires_at = NOW() - INTERVAL '1 minute'
        WHERE drawer_id = :drawer_id
    """), {"drawer_id": drawer_id})
    db.commit()

    # A second user should now see the space as available again
    resp2 = client.post("/api/v1/containers/allocate-proximity/", json={
        "number_of_containers": 5,
        "sample_type":          "study_sample_container",
        "freezer_asset_id":     "TEST-FRZ-01",
    })

    assert resp2.status_code == 200, (
        "Expired reservations must release space — the second suggest must succeed"
    )

    session.close()


# ── Test 4: Manual assignment respects active reservations ────────────────────

def test_manual_assignment_respects_reservations(freezer):
    """
    Scenario:
        A user runs a suggest that places an active reservation on a drawer
        for 4 out of 5 available slots. A second user then tries to manually
        assign 3 containers to the same drawer, which would exceed the
        1 remaining effective slot.

    Expected:
        The manual assignment endpoint calls available_space_in_drawer(),
        which subtracts the active reservation. Only 1 slot is effectively
        available, so assigning 3 is rejected with 409.

    What this validates:
        Manual assignment and the reservation-based allocation flow share
        the same capacity check. There is no bypass path — active reservations
        are always subtracted regardless of how a container is being introduced.
    """
    client1, s1 = make_client()
    client2, s2 = make_client()

    # User 1 reserves 4 out of 5 slots
    resp = client1.post("/api/v1/containers/allocate-proximity/", json={
        "number_of_containers": 4,
        "sample_type":          "study_sample_container",
        "freezer_asset_id":     "TEST-FRZ-01",
    })
    assert resp.status_code == 200
    drawer_id = resp.json()[0]["drawer_id"]

    # User 2 tries to manually assign 3 containers to the same drawer
    resp2 = client2.post("/api/v1/containers/manual/study-sample/", json={
        "drawer_id": drawer_id,
        "containers": [
            {"container_barcode": f"MANUAL-{i}", "study_name": "TEST"}
            for i in range(3)
        ],
    })

    print(f"\nManual assign status: {resp2.status_code} — {resp2.json()}")

    assert resp2.status_code == 409, (
        "Manual assignment must be blocked when active reservations leave "
        "insufficient effective capacity"
    )

    s1.close(); s2.close()
