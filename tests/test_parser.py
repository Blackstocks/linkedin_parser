from __future__ import annotations

import json

from app.linkedin.parser import parse_profile_payload
from app.linkedin.rsc import decode_rsc_payload
from tests.conftest import load_fixture


def test_parse_sdui_fixture() -> None:
    payload = json.loads(load_fixture("sdui_profile.json"))
    profile = parse_profile_payload(payload)

    assert profile.name == "Jane Doe"
    assert profile.headline == "Staff Software Engineer at Example Corp"
    assert profile.location == "San Francisco Bay Area"
    assert "backend systems" in profile.about
    assert profile.image_url.endswith("large.jpg")
    assert len(profile.experience) == 2
    assert profile.experience[0].title == "Staff Software Engineer"
    assert profile.experience[0].company == "Example Corp"
    assert profile.education[0].school == "Stanford University"
    assert profile.education[0].degree == "M.S. Computer Science"
    assert profile.skills == ["Python", "Distributed Systems", "FastAPI"]
    assert profile.certifications[0].name == "AWS Certified Solutions Architect"
    assert profile.languages[0].name == "English"
    assert profile.languages[1].name == "Spanish"


def test_parse_rsc_stream_fixture() -> None:
    payload = decode_rsc_payload(load_fixture("rsc_stream.txt"))
    profile = parse_profile_payload(payload)

    assert profile.name == "Alex Rivera"
    assert profile.headline == "Product Designer"
    assert profile.location == "Austin, Texas"
    assert profile.image_url.startswith("https://media.licdn.com/")
    assert profile.experience[0].company == "Horizon Labs"
    assert profile.education[0].school == "RISD"
    assert "Figma" in profile.skills


def test_parse_missing_fields_gracefully() -> None:
    payload = json.loads(load_fixture("empty_profile.json"))
    profile = parse_profile_payload(payload)

    assert profile.name == ""
    assert profile.headline == ""
    assert profile.about == ""
    assert profile.experience == []
    assert profile.education == []
    assert profile.skills == []
    assert profile.certifications == []
    assert profile.languages == []


def test_decode_plain_json() -> None:
    assert decode_rsc_payload('{"a": 1}') == {"a": 1}


def test_decode_empty() -> None:
    assert decode_rsc_payload("") == {}
