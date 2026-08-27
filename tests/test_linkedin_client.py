from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.linkedin.client import LinkedInClient
from app.linkedin.voyager import parse_voyager_profile


FULL_PROFILE = {
    "included": [
        {
            "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
            "entityUrn": "urn:li:fsd_profile:ACoAAAExample",
            "firstName": "Jane",
            "lastName": "Doe",
            "headline": "Staff Engineer",
            "geoLocationName": "San Francisco Bay Area",
            "summary": "Builds backend systems.",
        },
        {
            "$type": "com.linkedin.voyager.dash.identity.profile.Position",
            "title": "Staff Software Engineer",
            "companyName": "Example Corp",
            "dateRange": {"start": {"month": 1, "year": 2022}, "end": None},
            "description": "Led the profile API.",
        },
        {
            "$type": "com.linkedin.voyager.dash.identity.profile.Education",
            "schoolName": "Stanford University",
            "degreeName": "M.S.",
            "fieldOfStudy": "Computer Science",
            "dateRange": {
                "start": {"year": 2016},
                "end": {"year": 2018},
            },
        },
        {"$type": "com.linkedin.voyager.dash.identity.profile.Skill", "name": "Python"},
    ]
}


def test_parse_voyager_full_profile() -> None:
    profile = parse_voyager_profile(FULL_PROFILE)
    assert profile.name == "Jane Doe"
    assert profile.headline == "Staff Engineer"
    assert profile.experience[0].company == "Example Corp"
    assert profile.education[0].school == "Stanford University"
    assert profile.skills == ["Python"]


@pytest.mark.asyncio
async def test_fetch_profile_uses_voyager_identity() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        if request.url.path.endswith("/identity/dash/profiles"):
            return httpx.Response(200, json=FULL_PROFILE)
        return httpx.Response(500, text="should not call SDUI when Voyager succeeds")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://www.linkedin.com",
        transport=transport,
    ) as http:
        settings = Settings(
            linkedin_li_at="test-li-at",
            linkedin_jsessionid="ajax:12345",
        )
        client = LinkedInClient(settings, client=http)
        profile = await client.fetch_profile("jane-doe")

    assert profile.name == "Jane Doe"
    assert recorded[0].method == "GET"
    assert "memberIdentity=jane-doe" in str(recorded[0].url)
    assert all("/rsc-action/" not in str(req.url) for req in recorded)
    assert "li_at=test-li-at" in recorded[0].headers["cookie"]
