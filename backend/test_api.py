"""Run with:  python -m pytest -q   (pip install pytest)"""
import pytest
from app import create_app
from extensions import db


@pytest.fixture()
def client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.drop_all(); db.create_all()
        yield app.test_client()


def signup(c, name):
    r = c.post("/api/auth/signup", json={"username": name, "email": f"{name}@x.com", "password": "secret1"})
    return r, {"Authorization": f"Bearer {r.get_json()['token']}"}


def test_first_user_is_admin_second_is_sales(client):
    r1, _ = signup(client, "boss")
    r2, _ = signup(client, "rep")
    assert r1.get_json()["user"]["role"] == "admin"
    assert r2.get_json()["user"]["role"] == "sales"


def test_validation_and_auth(client):
    assert client.get("/api/customers").status_code == 401
    assert client.post("/api/auth/signup", json={"username": "a"}).status_code == 400
    _, h = signup(client, "boss")
    assert client.post("/api/customers", json={"name": "", "email": "bad"}, headers=h).status_code == 400
    assert client.post("/api/auth/login", json={"username": "boss", "password": "no"}).status_code == 401


def test_customer_lead_interaction_flow(client):
    _, admin = signup(client, "boss")
    _, rep = signup(client, "rep")
    cid = client.post("/api/customers", json={"name": "Amit", "email": "a@b.com"}, headers=rep).get_json()["id"]
    lead = client.post("/api/leads", json={"customer_id": cid}, headers=rep).get_json()
    assert lead["status"] == "new"
    assert client.patch(f"/api/leads/{lead['id']}", json={"status": "won"}, headers=rep).get_json()["status"] == "won"
    assert client.patch(f"/api/leads/{lead['id']}", json={"status": "bogus"}, headers=rep).status_code == 400
    r = client.post(f"/api/leads/{lead['id']}/interactions",
                    json={"interaction_type": "call", "description": "Intro call"}, headers=rep)
    assert r.status_code == 201
    stats = client.get("/api/dashboard/stats", headers=rep).get_json()
    assert stats["leads_by_status"]["won"] == 1 and len(stats["recent_interactions"]) == 1
    assert client.get("/api/leads?status=won", headers=rep).get_json()[0]["id"] == lead["id"]


def test_rbac(client):
    _, admin = signup(client, "boss")
    _, rep = signup(client, "rep")
    _, rep2 = signup(client, "rep2")
    cid = client.post("/api/customers", json={"name": "Amit", "email": "a@b.com"}, headers=rep).get_json()["id"]
    lead = client.post("/api/leads", json={"customer_id": cid}, headers=rep).get_json()
    assert client.get(f"/api/leads/{lead['id']}", headers=rep2).status_code == 403   # other rep
    assert client.get(f"/api/leads/{lead['id']}", headers=admin).status_code == 200  # admin sees all
    assert client.delete(f"/api/customers/{cid}", headers=rep).status_code == 403    # admin only
    assert client.delete(f"/api/customers/{cid}", headers=admin).status_code == 200


def test_logout_revokes_token(client):
    _, h = signup(client, "boss")
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_csv_export(client):
    _, h = signup(client, "boss")
    client.post("/api/customers", json={"name": "Amit", "email": "a@b.com"}, headers=h)
    r = client.get("/api/export/customers", headers=h)
    assert r.mimetype == "text/csv" and b"Amit" in r.data
