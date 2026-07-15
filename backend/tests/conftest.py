import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.models import Base

from pathlib import Path

VIEW_SQL = Path(__file__).parent.parent / "app" / "sql" / "drawer_coordinates.sql"

TEST_DB_URL = "postgresql://postgres:password@localhost:5432/freezer_test"

engine = create_engine(TEST_DB_URL)
TestingSession = sessionmaker(bind=engine)


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    """Recreate all tables before each test, drop after."""
    with engine.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS drawer_coordinates"))
    Base.metadata.drop_all(bind=engine)  # safety net in case a prior run left tables behind
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(VIEW_SQL.read_text()))
    yield
    with engine.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS drawer_coordinates"))
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def freezer(client):
    """Create a standard test freezer: 2 layers x 2 racks x 2 drawers = 8 drawers total."""
    resp = client.post("/api/v1/freezers/", json={
        "asset_id":               "TEST-FRZ-01",
        "temperature":            -80,
        "num_of_layers":          2,
        "num_of_rack_per_layer":  2,
        "num_of_drawer_per_rack": 2,
        "study_sample_capacity":  5,
        "stdqc_capacity":         8,
    })
    assert resp.status_code == 201
    return resp.json()
