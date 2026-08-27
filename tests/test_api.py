from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Profile


class StubLinkedInClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def fetch_profile(self, vanity_name: str) -> Profile:
        self.calls.append(vanity_name)
        return Profile(name="Jane Doe", headline="Engineer")

    async def aclose(self) -> None:
        return None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LINKEDIN_LI_AT", "test-li-at")
    monkeypatch.setenv("LINKEDIN_JSESSIONID", "ajax:123")
    from app.config import get_settings

    get_settings.cache_clear()
    stub = StubLinkedInClient()
    with TestClient(app) as test_client:
        test_client.app.state.linkedin_client = stub
        test_client.app.state.settings = get_settings()
        yield test_client
    get_settings.cache_clear()


def test_docs_is_available_without_openapi_json(client: TestClient) -> None:
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "swagger-ui" in docs.text
    assert client.get("/openapi.json").status_code == 404


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "li_at" in response.text
    assert "JSESSIONID" in response.text


def test_ready_reports_session(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"session_configured": True}


def test_profile_success(client: TestClient) -> None:
    response = client.post(
        "/profile",
        json={"linkedin_url": "https://www.linkedin.com/in/jane-doe/"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["name"] == "Jane Doe"
    assert body["profile"]["headline"] == "Engineer"
    assert body["profile"]["experience"] == []


def test_profile_incomplete_session(client: TestClient) -> None:
    response = client.post(
        "/profile",
        json={
            "linkedin_url": "https://www.linkedin.com/in/jane-doe/",
            "li_at": "only-one",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "incomplete_session"


def test_profile_invalid_url(client: TestClient) -> None:
    response = client.post(
        "/profile",
        json={"linkedin_url": "https://www.linkedin.com/company/example/"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_linkedin_url"
