import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    with flask_app.test_client() as c:
        yield c


# ── Route tests ──────────────────────────────────────────────


def test_homepage_returns_200(client):
    res = client.get("/")
    assert res.status_code == 200


def test_sitemap_returns_xml(client):
    res = client.get("/sitemap.xml")
    assert res.status_code == 200
    assert b"urlset" in res.data
    assert res.content_type.startswith("application/xml")


def test_robots_txt(client):
    res = client.get("/robots.txt")
    assert res.status_code == 200
    assert b"Sitemap" in res.data


def test_security_headers_present(client):
    res = client.get("/")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "strict-origin" in res.headers.get("Referrer-Policy", "")


# ── Contact form ─────────────────────────────────────────────


def _ajax_headers():
    return {"X-Requested-With": "fetch", "Accept": "application/json"}


def test_contact_post_valid_json(client):
    res = client.post(
        "/contact",
        data={
            "name": "Test User",
            "email": "test@example.com",
            "phone": "9000101213",
            "country": "United Kingdom",
            "query": "I need visa help for the UK.",
        },
        headers=_ajax_headers(),
    )
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True


def test_contact_post_missing_fields(client):
    res = client.post(
        "/contact",
        data={"name": "Only Name"},
        headers=_ajax_headers(),
    )
    assert res.status_code == 400
    assert res.get_json()["success"] is False


def test_contact_post_invalid_email(client):
    res = client.post(
        "/contact",
        data={
            "name": "Test",
            "email": "not-an-email",
            "phone": "9000101213",
            "country": "Canada",
            "query": "Hello",
        },
        headers=_ajax_headers(),
    )
    assert res.status_code == 400
    assert res.get_json()["success"] is False


def test_contact_accepts_message_field(client):
    """The /contact route also accepts 'message' as an alias for 'query'."""
    res = client.post(
        "/contact",
        data={
            "name": "Aisha",
            "email": "aisha@example.com",
            "phone": "9000101213",
            "country": "Australia",
            "message": "Australia student visa requirements?",
        },
        headers=_ajax_headers(),
    )
    assert res.status_code == 200
    assert res.get_json()["success"] is True


def test_contact_post_redirects_when_not_ajax(client):
    res = client.post(
        "/contact",
        data={
            "name": "Test",
            "email": "test@example.com",
            "phone": "9000101213",
            "country": "Canada",
            "query": "Standard form submission",
        },
    )
    assert res.status_code in (301, 302)


# ── Content tests ────────────────────────────────────────────


def test_homepage_has_meta_description(client):
    res = client.get("/")
    assert b'meta name="description"' in res.data


def test_homepage_has_canonical(client):
    res = client.get("/")
    assert b'rel="canonical"' in res.data


def test_homepage_has_og_tags(client):
    res = client.get("/")
    assert b'og:title' in res.data
    assert b'og:description' in res.data


def test_homepage_has_skip_link(client):
    res = client.get("/")
    assert b'sv-skip-link' in res.data


def test_homepage_uses_target_keywords(client):
    res = client.get("/")
    body = res.data.lower()
    assert b"student visa consultant" in body
    assert b"canada study permit" in body
    assert b"australia student visa" in body


def test_no_ai_phrases_in_homepage(client):
    res = client.get("/")
    body = res.data.lower()
    bad_phrases = [
        b"navigating the complexities",
        b"cutting-edge",
        b"holistic approach",
        b"leverage",
        b"tailored solutions",
        b"seamlessly",
        b"unlock your potential",
    ]
    for phrase in bad_phrases:
        assert phrase not in body, f"AI phrase found: {phrase.decode()}"


# ── Legacy redirects ─────────────────────────────────────────


def test_legacy_admin_redirects(client):
    res = client.get("/admin")
    assert res.status_code in (301, 302)
