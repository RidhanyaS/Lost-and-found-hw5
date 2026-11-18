import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))

    from app import app
    from db import init_db

    app.config["DATABASE"] = str(database_path)
    app.config["TESTING"] = True
    with app.app_context():
        init_db()

    yield app.test_client()


def test_home_page_returns_success(client):
    response = client.get("/")

    assert response.status_code == 200


def test_nonexistent_route_returns_not_found(client):
    response = client.get("/this-page-does-not-exist")

    assert response.status_code == 404


def test_home_page_displays_seeded_item(client):
    response = client.get("/")

    assert b"Blue stainless steel water bottle" in response.data
