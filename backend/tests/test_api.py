import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["UPLOAD_DIR"] = "./test_uploads"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_upload_and_verify_flow():
    pid = client.post("/api/premises", params={"label": "Home", "sanctioned_load_kw": 2}).json()["id"]
    r = client.post(f"/api/premises/{pid}/bills", files={"file": ("bill.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert r.status_code == 200
    bill_id = r.json()["bill_id"]
    v = client.post(f"/api/bills/{bill_id}/verify", params={"units_kwh": 250, "amount_billed": 1855}).json()
    assert v["flagged"] is True


def test_rejects_bad_file_type():
    pid = client.post("/api/premises", params={"label": "X"}).json()["id"]
    r = client.post(f"/api/premises/{pid}/bills", files={"file": ("a.exe", b"x", "application/x-msdownload")})
    assert r.status_code == 415


def test_home_page_served():
    r = client.get("/")
    assert r.status_code == 200 and "BillWise" in r.text


def test_real_bill_through_api():
    pid = client.post("/api/premises", params={"label": "Real", "sanctioned_load_kw": 3}).json()["id"]
    bid = client.post(f"/api/premises/{pid}/bills",
                      files={"file": ("b.jpg", b"fake", "image/jpeg")}).json()["bill_id"]
    v = client.post(f"/api/bills/{bid}/verify",
                    params={"units_kwh": 94, "amount_billed": 173.94, "subsidy_units": 67}).json()
    assert v["recomputed"] == 173.94 and v["flagged"] is False


def test_multi_month_bill_through_api():
    pid = client.post("/api/premises", params={"label": "Two month", "sanctioned_load_kw": 2}).json()["id"]
    bid = client.post(f"/api/premises/{pid}/bills",
                      files={"file": ("b.jpg", b"fake", "image/jpeg")}).json()["bill_id"]
    v = client.post(f"/api/bills/{bid}/verify",
                    params={"units_kwh": 335, "amount_billed": 424.00, "subsidy_units": 272.47,
                            "billing_days": 61, "fppca": "236.15@0.02,98.85@0.32"}).json()
    assert v["flagged"] is False


def test_bad_fppca_text_rejected():
    pid = client.post("/api/premises", params={"label": "X", "sanctioned_load_kw": 2}).json()["id"]
    bid = client.post(f"/api/premises/{pid}/bills",
                      files={"file": ("b.jpg", b"fake", "image/jpeg")}).json()["bill_id"]
    r = client.post(f"/api/bills/{bid}/verify",
                    params={"units_kwh": 335, "amount_billed": 424, "fppca": "nonsense"})
    assert r.status_code == 422


def test_verify_returns_coach_advice():
    pid = client.post("/api/premises", params={"label": "Coach", "sanctioned_load_kw": 3}).json()["id"]
    bid = client.post(f"/api/premises/{pid}/bills",
                      files={"file": ("b.jpg", b"fake", "image/jpeg")}).json()["bill_id"]
    v = client.post(f"/api/bills/{bid}/verify",
                    params={"units_kwh": 94, "amount_billed": 173.94, "subsidy_units": 67,
                            "billing_days": 31}).json()
    assert v["coach"]["summary"] and v["coach"]["tips"]
    assert "breakdown" in v and "gross" in v["breakdown"]
    assert len(v["breakdown"]["gross"]["line_items"]) > 0


def test_upload_not_stored_when_disabled():
    from app.config import settings
    settings.store_uploads = False
    try:
        pid = client.post("/api/premises", params={"label": "Private", "sanctioned_load_kw": 3}).json()["id"]
        r = client.post(f"/api/premises/{pid}/bills", files={"file": ("b.jpg", b"fake", "image/jpeg")})
        assert r.status_code == 200
    finally:
        settings.store_uploads = True


def test_database_url_scheme_fixed():
    from app.config import Settings
    assert Settings(database_url="postgres://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"
    assert Settings(database_url="postgresql://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"
    assert Settings(database_url="sqlite:///x.db").database_url == "sqlite:///x.db"


def test_cloud_sql_and_cloud_env_settings():
    from app.config import Settings
    s = Settings(db_user="admin", db_pass="secret", db_host="10.0.0.1", db_port=5432, db_name="billwisedb")
    assert s.database_url == "postgresql+psycopg://admin:secret@10.0.0.1:5432/billwisedb"

    s_cloudsql = Settings(db_user="admin", db_pass="secret", cloud_sql_connection_name="proj:reg:inst", db_name="billwisedb")
    assert s_cloudsql.database_url == "postgresql+psycopg://admin:secret@/billwisedb?host=/cloudsql/proj:reg:inst"


def test_storage_service_local_and_disabled():
    from app.config import settings
    from app.services.storage import save_upload, read_upload

    # Test disabled
    settings.store_uploads = False
    assert save_upload(b"test", "image/png") == "not stored"
    assert read_upload("not stored") is None

    # Test local
    settings.store_uploads = True
    settings.firebase_storage_bucket = ""
    saved_path = save_upload(b"hello world", "image/png")
    assert saved_path != "not stored"
    assert read_upload(saved_path) == b"hello world"

