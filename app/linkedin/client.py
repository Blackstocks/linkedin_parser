from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import Settings
from app.errors import LinkedInAuthError, LinkedInUpstreamError, ProfileNotFoundError
from app.linkedin.parser import parse_profile_payload
from app.linkedin.rsc import decode_rsc_payload
from app.linkedin.voyager import parse_voyager_profile
from app.models import Profile

logger = logging.getLogger(__name__)

COMPONENT_PATH = "/flagship-web/rsc-action/actions/component"
IDENTITY_PATH = "/voyager/api/identity/dash/profiles"
GRAPHQL_PATH = "/voyager/api/graphql"
PROFILE_URN_RE = re.compile(r"urn:li:fsd_profile:([A-Za-z0-9_-]+)")

IDENTITY_DECORATIONS = (
    "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93",
    "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-63",
    "com.linkedin.voyager.dash.deco.identity.profile.TopCardSupplementary-166",
    "com.linkedin.voyager.dash.deco.identity.profile.WebTopCardCore-16",
)

GRAPHQL_QUERY_IDS = (
    "voyagerIdentityDashProfiles.e9b0809465a07db1f02e70a82d455e10",
    "voyagerIdentityDashProfileCards.aec4c2601fac8c5f615c7630b8db1ab3",
    "voyagerIdentityDashProfileCards.2d68c43b54ee24f8de25bc423c3cf7e4",
)


class LinkedInClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url="https://www.linkedin.com",
            timeout=settings.request_timeout_seconds,
            follow_redirects=False,
        )
        self._seed_cookies()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_profile(self, vanity_name: str) -> Profile:
        voyager_payload = await self._fetch_identity_profile(vanity_name)
        profile = parse_voyager_profile(voyager_payload) if voyager_payload is not None else Profile()

        if not _has_core_fields(profile):
            gql_payload = await self._fetch_graphql_profile(vanity_name)
            if gql_payload is not None:
                merged = parse_voyager_profile(gql_payload)
                profile = _prefer_filled(profile, merged)

        if not _has_core_fields(profile):
            profile_id = _profile_id_from_payload(voyager_payload) or ""
            raw = await self._try_sdui_component(vanity_name, profile_id)
            if raw:
                profile = _prefer_filled(profile, parse_profile_payload(decode_rsc_payload(raw)))

        if not _has_core_fields(profile):
            logger.warning("Parsed profile for %s was empty after Voyager/SDUI reads", vanity_name)
            raise ProfileNotFoundError(vanity_name)
        return profile

    async def _fetch_identity_profile(self, vanity_name: str) -> Any | None:
        last_error: LinkedInUpstreamError | LinkedInAuthError | None = None
        for decoration in IDENTITY_DECORATIONS:
            try:
                response = await self._request(
                    "GET",
                    IDENTITY_PATH,
                    params={
                        "q": "memberIdentity",
                        "memberIdentity": vanity_name,
                        "decorationId": decoration,
                    },
                    headers=self._voyager_headers(vanity_name),
                )
            except LinkedInAuthError:
                raise
            except LinkedInUpstreamError as exc:
                last_error = exc
                logger.info("Identity decoration %s failed: %s", decoration, exc)
                continue
            try:
                payload = response.json()
            except json.JSONDecodeError:
                continue
            logger.info(
                "Identity profile vanity=%s decoration=%s bytes=%s",
                vanity_name,
                decoration.rsplit(".", 1)[-1],
                len(response.content),
            )
            return payload
        if last_error:
            raise last_error
        return None

    async def _fetch_graphql_profile(self, vanity_name: str) -> Any | None:
        for query_id in GRAPHQL_QUERY_IDS:
            url = (
                f"{GRAPHQL_PATH}?includeWebMetadata=true"
                f"&variables=(vanityName:{vanity_name})&queryId={query_id}"
            )
            try:
                response = await self._request(
                    "GET",
                    url,
                    headers=self._voyager_headers(vanity_name),
                )
            except (LinkedInUpstreamError, LinkedInAuthError) as exc:
                logger.info("GraphQL %s failed: %s", query_id, exc)
                continue
            try:
                return response.json()
            except json.JSONDecodeError:
                continue
        return None

    async def _try_sdui_component(self, vanity_name: str, viewee_profile_id: str) -> str:
        if not viewee_profile_id:
            return ""
        component_id = self._settings.linkedin_component_id
        body = {
            "vanityName": vanity_name,
            "vieweeProfileId": viewee_profile_id,
            "isSelfView": False,
            "profileComponentState": {},
        }
        try:
            response = await self._request(
                "POST",
                COMPONENT_PATH,
                params={"componentId": component_id},
                json=body,
                headers=self._sdui_headers(vanity_name),
            )
        except (LinkedInUpstreamError, LinkedInAuthError) as exc:
            logger.warning("SDUI component request failed (%s); continuing with Voyager data", exc)
            return ""
        logger.info("Fetched SDUI component for vanity=%s bytes=%s", vanity_name, len(response.content))
        return response.text

    def _seed_cookies(self) -> None:
        self._set_cookie("li_at", self._settings.linkedin_li_at, "www.linkedin.com")
        self._set_cookie("JSESSIONID", self._settings.linkedin_jsessionid, "www.linkedin.com")
        for name, value in _parse_cookie_fragment(self._settings.linkedin_extra_cookies).items():
            domain = (
                "www.linkedin.com"
                if name.lower() in {"li_at", "jsessionid", "bscookie"}
                else "linkedin.com"
            )
            self._set_cookie(name, value, domain)

    def _set_cookie(self, name: str, value: str, domain: str) -> None:
        cleaned = value.strip().strip('"').strip("'")
        if not name or not cleaned:
            return
        self._client.cookies.set(name, cleaned, domain=domain)

    def _live_csrf_token(self) -> str:
        current = self._client.cookies.get("JSESSIONID") or self._settings.csrf_token()
        return str(current).strip().strip('"')

    def _common_headers(self, vanity_name: str | None = None) -> dict[str, str]:
        referer = (
            f"https://www.linkedin.com/in/{vanity_name}/"
            if vanity_name
            else "https://www.linkedin.com/feed/"
        )
        headers = {
            "user-agent": self._settings.linkedin_user_agent,
            "accept-language": "en-US,en;q=0.9",
            "csrf-token": self._live_csrf_token(),
            "x-li-lang": "en_US",
            "origin": "https://www.linkedin.com",
            "referer": referer,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
        headers.update(self._settings.extra_headers())
        return headers

    def _voyager_headers(self, vanity_name: str | None = None) -> dict[str, str]:
        headers = self._common_headers(vanity_name)
        headers.update(
            {
                "accept": "application/vnd.linkedin.normalized+json+2.1",
                "x-restli-protocol-version": "2.0.0",
            }
        )
        return headers

    def _sdui_headers(self, vanity_name: str | None = None) -> dict[str, str]:
        version = self._settings.linkedin_sdui_client_version
        headers = self._common_headers(vanity_name)
        track = {
            "clientVersion": version,
            "mpVersion": version,
            "osName": "web",
            "timezoneOffset": 0,
            "timezone": "UTC",
            "mpName": "web",
            "displayWidth": 1440,
            "displayHeight": 900,
        }
        headers.update(
            {
                "accept": "application/json, text/x-component, */*",
                "content-type": "application/json",
                "x-li-rsc-stream": "true",
                "x-li-application-version": version,
                "x-li-track": json.dumps(track, separators=(",", ":")),
            }
        )
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            response = await self._client.request(
                method,
                path,
                params=params,
                json=json,
                headers=headers or self._common_headers(),
            )
        except httpx.HTTPError as exc:
            logger.exception("LinkedIn request failed: %s %s", method, path)
            raise LinkedInUpstreamError(f"LinkedIn request failed: {exc}") from exc

        location = response.headers.get("location", "")
        if response.status_code in {301, 302, 303, 307, 308}:
            if "login" in location.lower() or "uas/authenticate" in location.lower():
                raise LinkedInAuthError()
            raise LinkedInAuthError(
                "LinkedIn redirected the request. Refresh LINKEDIN_LI_AT and "
                "LINKEDIN_JSESSIONID, and add bcookie and lidc to LINKEDIN_EXTRA_COOKIES."
            )
        if response.status_code in {401, 403}:
            raise LinkedInAuthError(
                f"LinkedIn rejected the session (HTTP {response.status_code}). "
                "Refresh LINKEDIN_LI_AT and LINKEDIN_JSESSIONID from your browser."
            )
        if response.status_code == 404:
            raise LinkedInUpstreamError("LinkedIn returned 404 for this profile request", status_code=404)
        if response.status_code == 429:
            raise LinkedInUpstreamError(
                "LinkedIn returned HTTP 429. Wait and retry; this service does not override rate limits.",
                status_code=429,
            )
        if response.status_code == 999:
            raise LinkedInUpstreamError(
                "LinkedIn denied the request (HTTP 999). Copy bcookie and lidc from "
                "DevTools → Application → Cookies into LINKEDIN_EXTRA_COOKIES, refresh li_at, "
                "and restart the server.",
                status_code=502,
            )
        if response.status_code >= 400:
            snippet = response.text[:180].replace("\n", " ")
            logger.error(
                "LinkedIn upstream error method=%s path=%s status=%s body=%s",
                method,
                path,
                response.status_code,
                snippet,
            )
            raise LinkedInUpstreamError(
                f"LinkedIn returned HTTP {response.status_code}",
                status_code=502,
            )
        return response


def _parse_cookie_fragment(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in raw.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and value:
            cookies[name] = value
    return cookies


def _has_core_fields(profile: Profile) -> bool:
    return bool(profile.name or profile.headline or profile.experience or profile.education)


def _prefer_filled(base: Profile, extra: Profile) -> Profile:
    data = base.model_dump()
    other = extra.model_dump()
    for key, value in other.items():
        if not data.get(key) and value:
            data[key] = value
    return Profile.model_validate(data)


def _profile_id_from_payload(payload: Any) -> str:
    if payload is None:
        return ""
    blob = json.dumps(payload)
    match = PROFILE_URN_RE.search(blob)
    return match.group(1) if match else ""
