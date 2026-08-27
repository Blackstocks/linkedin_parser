from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from app.errors import InvalidLinkedInUrlError

_PROFILE_PATH = re.compile(
    r"^/in/(?P<vanity>[^/]+)/?(?:$|[?#])",
    re.IGNORECASE,
)
_ALLOWED_HOSTS = {"linkedin.com", "www.linkedin.com", "linkedin.cn", "www.linkedin.cn"}


def extract_vanity_name(linkedin_url: str) -> str:
    """Return the public profile slug from a LinkedIn profile URL."""
    parsed = urlparse(str(linkedin_url).strip())
    if parsed.scheme not in {"http", "https"}:
        raise InvalidLinkedInUrlError("linkedin_url must use http or https")

    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host_key = host
    else:
        host_key = host
    if host_key not in _ALLOWED_HOSTS and not host_key.endswith(".linkedin.com"):
        raise InvalidLinkedInUrlError("linkedin_url must point to linkedin.com")

    path = unquote(parsed.path or "")
    match = _PROFILE_PATH.match(path)
    if not match:
        raise InvalidLinkedInUrlError(
            "linkedin_url must look like https://www.linkedin.com/in/<vanity-name>/"
        )

    vanity = match.group("vanity").strip()
    vanity = vanity.split("?")[0].strip("/")
    if not vanity or vanity.lower() in {"in", "pub"}:
        raise InvalidLinkedInUrlError("could not extract a vanity name from linkedin_url")
    return vanity
