from __future__ import annotations

from typing import Any

from app.linkedin.parser import parse_profile_payload
from app.models import (
    CertificationItem,
    EducationItem,
    ExperienceItem,
    LanguageItem,
    Profile,
)


def parse_voyager_profile(payload: Any) -> Profile:
    """Normalize a Voyager identity/dash or GraphQL profile payload."""
    typed = _index_by_type(payload)
    profile_node = _first_profile_node(typed) or {}
    fallback = parse_profile_payload(payload)

    first = _text(profile_node.get("firstName"))
    last = _text(profile_node.get("lastName"))
    name = f"{first} {last}".strip() or fallback.name
    headline = _text(profile_node.get("headline")) or fallback.headline
    location = (
        _text(profile_node.get("geoLocationName"))
        or _text(profile_node.get("locationName"))
        or _text(profile_node.get("formattedLocation"))
        or fallback.location
    )
    about = _text(profile_node.get("summary")) or fallback.about
    image_url = _picture_url(profile_node) or fallback.image_url

    experience = _positions(typed.get("position", []) + typed.get("profileposition", []))
    education = _schools(typed.get("education", []) + typed.get("profileeducation", []))
    skills = _skills(typed.get("skill", []) + typed.get("profileskill", []))
    certifications = _certs(
        typed.get("certification", []) + typed.get("profilecertification", [])
    )
    languages = _langs(typed.get("language", []) + typed.get("profilelanguage", []))

    return Profile(
        name=name or fallback.name,
        headline=headline,
        location=location,
        about=about,
        image_url=image_url,
        experience=experience or fallback.experience,
        education=education or fallback.education,
        skills=skills or fallback.skills,
        certifications=certifications or fallback.certifications,
        languages=languages or fallback.languages,
    )


def _walk(node: Any):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "value"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return ""


def _index_by_type(payload: Any) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        type_name = str(node.get("$type") or "")
        if not type_name:
            continue
        leaf = type_name.rsplit(".", 1)[-1].lower()
        grouped.setdefault(leaf, []).append(node)
    return grouped


def _first_profile_node(typed: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    for key in ("profile", "miniprofile"):
        nodes = typed.get(key) or []
        for node in nodes:
            if node.get("firstName") or node.get("headline"):
                return node
    return None


def _picture_url(profile_node: dict[str, Any]) -> str:
    for node in _walk(profile_node):
        if not isinstance(node, dict):
            continue
        if "rootUrl" in node and "artifacts" in node:
            artifacts = node.get("artifacts") or []
            if not isinstance(artifacts, list) or not artifacts:
                continue
            widest = max(
                (item for item in artifacts if isinstance(item, dict)),
                key=lambda item: int(item.get("width") or 0),
                default={},
            )
            segment = widest.get("fileIdentifyingUrlPathSegment")
            root = node.get("rootUrl")
            if isinstance(root, str) and isinstance(segment, str):
                return f"{root}{segment}"
        for key in ("url", "displayImageUrl"):
            value = node.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
    return ""


def _date_range(node: dict[str, Any]) -> str:
    dr = node.get("dateRange") or node.get("timePeriod")
    if not isinstance(dr, dict):
        return _text(node.get("caption"))
    start = _date_part(dr.get("start") or dr.get("startDate"))
    end = _date_part(dr.get("end") or dr.get("endDate")) or "Present"
    if not start:
        return ""
    return f"{start} - {end}"


def _date_part(part: Any) -> str:
    if not isinstance(part, dict):
        return ""
    year = part.get("year")
    month = part.get("month")
    if year and month:
        return f"{int(month):02d}/{year}"
    if year:
        return str(year)
    return ""


def _positions(nodes: list[dict[str, Any]]) -> list[ExperienceItem]:
    items: list[ExperienceItem] = []
    seen: set[tuple[str, str, str]] = set()
    for node in nodes:
        title = _text(node.get("title"))
        company = _text(node.get("companyName") or node.get("subtitle"))
        dates = _date_range(node)
        key = (title, company, dates)
        if not title or key in seen:
            continue
        seen.add(key)
        items.append(
            ExperienceItem(
                title=title,
                company=company,
                location=_text(node.get("geoLocationName") or node.get("locationName")),
                dates=dates,
                description=_text(node.get("description")),
            )
        )
    return items


def _schools(nodes: list[dict[str, Any]]) -> list[EducationItem]:
    items: list[EducationItem] = []
    seen: set[tuple[str, str]] = set()
    for node in nodes:
        school = _text(node.get("schoolName") or node.get("title"))
        degree = _text(node.get("degreeName") or node.get("degree") or node.get("subtitle"))
        field = _text(node.get("fieldOfStudy"))
        dates = _date_range(node)
        key = (school, degree)
        if not school or key in seen:
            continue
        seen.add(key)
        items.append(EducationItem(school=school, degree=degree, field=field, dates=dates))
    return items


def _skills(nodes: list[dict[str, Any]]) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        name = _text(node.get("name") or node.get("skillName") or node.get("title"))
        if not name or name in seen:
            continue
        seen.add(name)
        skills.append(name)
    return skills


def _certs(nodes: list[dict[str, Any]]) -> list[CertificationItem]:
    items: list[CertificationItem] = []
    seen: set[str] = set()
    for node in nodes:
        name = _text(node.get("name") or node.get("title"))
        if not name or name in seen:
            continue
        seen.add(name)
        items.append(
            CertificationItem(
                name=name,
                issuer=_text(node.get("authority") or node.get("companyName") or node.get("subtitle")),
                date=_date_range(node) or _text(node.get("displaySource")),
            )
        )
    return items


def _langs(nodes: list[dict[str, Any]]) -> list[LanguageItem]:
    items: list[LanguageItem] = []
    seen: set[str] = set()
    for node in nodes:
        name = _text(node.get("name") or node.get("title"))
        if not name or name in seen:
            continue
        seen.add(name)
        items.append(
            LanguageItem(
                name=name,
                proficiency=_text(node.get("proficiency") or node.get("subtitle")),
            )
        )
    return items
