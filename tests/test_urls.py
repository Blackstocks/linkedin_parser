from __future__ import annotations

import pytest

from app.errors import InvalidLinkedInUrlError
from app.urls import extract_vanity_name


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.linkedin.com/in/jane-doe/", "jane-doe"),
        ("https://linkedin.com/in/jane-doe", "jane-doe"),
        ("https://www.linkedin.com/in/jane-doe?trk=share", "jane-doe"),
        ("http://www.linkedin.com/in/Ada_Lovelace/", "Ada_Lovelace"),
    ],
)
def test_extract_vanity_name(url: str, expected: str) -> None:
    assert extract_vanity_name(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://www.linkedin.com/company/example/",
        "https://example.com/in/jane-doe/",
        "ftp://www.linkedin.com/in/jane-doe/",
        "https://www.linkedin.com/in/",
    ],
)
def test_extract_vanity_name_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        extract_vanity_name(url)
