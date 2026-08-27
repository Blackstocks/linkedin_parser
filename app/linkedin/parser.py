from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.models import (
    CertificationItem,
    EducationItem,
    ExperienceItem,
    LanguageItem,
    Profile,
)

SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "about": ("about", "summary", "overview"),
    "experience": ("experience", "work experience"),
    "education": ("education",),
    "skills": ("skills", "top skills"),
    "certifications": (
        "licenses & certifications",
        "licenses and certifications",
        "certifications",
        "licenses",
    ),
    "languages": ("languages",),
}

SKIP_TEXT_KEYS = {
    "accessibilityText",
    "actionTarget",
    "trackingId",
    "controlName",
    "pageKey",
}


def parse_profile_payload(payload: Any) -> Profile:
    """Walk an SDUI/RSC tree and normalize visible profile fields."""
    intro = _extract_intro(payload)
    sections = _collect_sections(payload)

    about = _first_long_text(sections.get("about") or [])
    if not about:
        about = intro.get("about", "")

    return Profile(
        name=intro.get("name", ""),
        headline=intro.get("headline", ""),
        location=intro.get("location", ""),
        about=about,
        image_url=intro.get("image_url") or _first_image_url(payload),
        experience=_parse_experience(sections.get("experience") or []),
        education=_parse_education(sections.get("education") or []),
        skills=_parse_skills(sections.get("skills") or []),
        certifications=_parse_certifications(sections.get("certifications") or []),
        languages=_parse_languages(sections.get("languages") or []),
    )


def _walk(node: Any) -> Iterator[Any]:
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        for key in ("text", "title", "name", "value", "stringValue"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
            if isinstance(inner, dict):
                nested = _as_text(inner)
                if nested:
                    return nested
        localized = value.get("localized")
        if isinstance(localized, dict):
            for item in localized.values():
                text = _as_text(item)
                if text:
                    return text
        attributed = value.get("attributedText") or value.get("textV2")
        if attributed is not None:
            return _as_text(attributed)
    if isinstance(value, list):
        parts = [_as_text(item) for item in value]
        return " ".join(part for part in parts if part).strip()
    return ""


def _node_title(node: dict[str, Any]) -> str:
    for key in ("title", "headline", "header", "text"):
        if key in node:
            text = _as_text(node[key])
            if text:
                return text
    return ""


def _classify_section(title: str) -> str | None:
    normalized = title.strip().lower()
    for section, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return section
    return None


def _collect_sections(payload: Any) -> dict[str, list[dict[str, Any]]]:
    sections: dict[str, list[dict[str, Any]]] = {key: [] for key in SECTION_ALIASES}
    current: str | None = None

    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        type_name = str(node.get("$type") or node.get("componentId") or "").lower()
        title = _node_title(node)
        classified = _classify_section(title) if title else None
        if classified:
            current = classified
            if any(key in node for key in ("items", "components", "text", "description", "summary")):
                sections[classified].append(node)
            continue
        for section, needle in (
            ("about", "about"),
            ("experience", "experience"),
            ("education", "education"),
            ("skills", "skill"),
            ("certifications", "certif"),
            ("languages", "language"),
        ):
            if needle in type_name:
                current = section
                sections[section].append(node)
                break
        else:
            if current and _looks_like_card(node):
                sections[current].append(node)
    return sections


def _looks_like_card(node: dict[str, Any]) -> bool:
    keys = set(node)
    card_keys = {
        "title",
        "subtitle",
        "caption",
        "description",
        "text",
        "insightText",
        "primarySubtitle",
        "secondarySubtitle",
        "items",
        "components",
        "name",
        "proficiency",
        "skillName",
        "companyName",
        "schoolName",
    }
    return bool(keys & card_keys)


def _extract_intro(payload: Any) -> dict[str, str]:
    name = ""
    headline = ""
    location = ""
    about = ""
    image_url = ""
    first_name = ""
    last_name = ""

    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        if not name:
            for key in ("fullName", "name", "formattedName"):
                candidate = _as_text(node.get(key))
                if candidate and " " in candidate and len(candidate) < 120:
                    name = candidate
                    break
        first_name = first_name or _as_text(node.get("firstName"))
        last_name = last_name or _as_text(node.get("lastName"))
        if not headline:
            for key in ("headline", "occupation", "tagline"):
                candidate = _as_text(node.get(key))
                if candidate:
                    headline = candidate
                    break
        if not location:
            for key in ("location", "geoLocationName", "locationName", "formattedLocation"):
                candidate = _as_text(node.get(key))
                if candidate:
                    location = candidate
                    break
        if not about:
            for key in ("summary", "about", "bio"):
                candidate = _as_text(node.get(key))
                if len(candidate) > 40:
                    about = candidate
                    break
        if not image_url:
            image_url = _image_from_node(node)

    if not name and (first_name or last_name):
        name = f"{first_name} {last_name}".strip()

    if not name or not headline or not location:
        top = _guess_top_card(payload)
        name = name or top.get("name", "")
        headline = headline or top.get("headline", "")
        location = location or top.get("location", "")

    return {
        "name": name,
        "headline": headline,
        "location": location,
        "about": about,
        "image_url": image_url,
    }


def _guess_top_card(payload: Any) -> dict[str, str]:
    """Use the first prominent title/subtitle/caption cluster as the top card."""
    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        title = _as_text(node.get("title"))
        subtitle = _as_text(node.get("subtitle") or node.get("primarySubtitle"))
        caption = _as_text(node.get("caption") or node.get("secondarySubtitle"))
        if title and subtitle and not _classify_section(title):
            return {"name": title, "headline": subtitle, "location": caption}
    return {}


def _image_from_node(node: dict[str, Any]) -> str:
    if "rootUrl" in node and "artifacts" in node:
        return _vector_image_url(node)
    for key in ("url", "src", "imageUrl", "displayImageUrl"):
        value = node.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return ""


def _vector_image_url(node: dict[str, Any]) -> str:
    root = node.get("rootUrl")
    artifacts = node.get("artifacts")
    if not isinstance(root, str) or not isinstance(artifacts, list) or not artifacts:
        return ""
    widest = max(
        (item for item in artifacts if isinstance(item, dict)),
        key=lambda item: int(item.get("width") or 0),
        default={},
    )
    segment = widest.get("fileIdentifyingUrlPathSegment")
    if not isinstance(segment, str):
        return ""
    return f"{root}{segment}"


def _first_image_url(payload: Any) -> str:
    for node in _walk(payload):
        if isinstance(node, dict):
            url = _image_from_node(node)
            if url:
                return url
    return ""


def _parse_experience(nodes: list[dict[str, Any]]) -> list[ExperienceItem]:
    items: list[ExperienceItem] = []
    seen: set[tuple[str, str, str]] = set()
    for node in nodes:
        title = _as_text(node.get("title"))
        company = _as_text(node.get("subtitle") or node.get("companyName") or node.get("company"))
        dates = _as_text(node.get("caption") or node.get("dateRange") or node.get("dates"))
        location = _as_text(node.get("metadata") or node.get("location"))
        description = _as_text(node.get("description") or node.get("text"))
        if not title and not company:
            continue
        key = (title, company, dates)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            ExperienceItem(
                title=title,
                company=company,
                location=location,
                dates=dates,
                description=description,
            )
        )
    return items


def _parse_education(nodes: list[dict[str, Any]]) -> list[EducationItem]:
    items: list[EducationItem] = []
    seen: set[tuple[str, str, str]] = set()
    for node in nodes:
        school = _as_text(node.get("title") or node.get("schoolName") or node.get("school"))
        degree = _as_text(node.get("subtitle") or node.get("degreeName") or node.get("degree"))
        field = _as_text(node.get("fieldOfStudy") or node.get("field"))
        dates = _as_text(node.get("caption") or node.get("dateRange") or node.get("dates"))
        if not school:
            continue
        key = (school, degree, dates)
        if key in seen:
            continue
        seen.add(key)
        items.append(EducationItem(school=school, degree=degree, field=field, dates=dates))
    return items


def _parse_skills(nodes: list[dict[str, Any]]) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        candidates = [
            _as_text(node.get("title")),
            _as_text(node.get("name")),
            _as_text(node.get("text")),
            _as_text(node.get("skillName")),
        ]
        nested = node.get("items") or node.get("components")
        if isinstance(nested, list):
            for child in nested:
                if isinstance(child, dict):
                    candidates.append(_as_text(child.get("title") or child.get("text") or child.get("name")))
        for skill in candidates:
            if not skill or skill.lower() in SECTION_ALIASES["skills"] or skill in seen:
                continue
            if len(skill) > 80:
                continue
            seen.add(skill)
            skills.append(skill)
    return skills


def _parse_certifications(nodes: list[dict[str, Any]]) -> list[CertificationItem]:
    items: list[CertificationItem] = []
    seen: set[tuple[str, str]] = set()
    for node in nodes:
        name = _as_text(node.get("title") or node.get("name"))
        issuer = _as_text(node.get("subtitle") or node.get("authority") or node.get("issuer"))
        date = _as_text(node.get("caption") or node.get("date"))
        if not name or name.lower() in SECTION_ALIASES["certifications"]:
            continue
        key = (name, issuer)
        if key in seen:
            continue
        seen.add(key)
        items.append(CertificationItem(name=name, issuer=issuer, date=date))
    return items


def _parse_languages(nodes: list[dict[str, Any]]) -> list[LanguageItem]:
    items: list[LanguageItem] = []
    seen: set[str] = set()
    for node in nodes:
        name = _as_text(node.get("title") or node.get("name"))
        proficiency = _as_text(node.get("subtitle") or node.get("proficiency") or node.get("caption"))
        if not name or name.lower() in SECTION_ALIASES["languages"]:
            continue
        if name in seen:
            continue
        seen.add(name)
        items.append(LanguageItem(name=name, proficiency=proficiency))
    return items


def _first_long_text(nodes: list[dict[str, Any]]) -> str:
    section_titles = {alias for aliases in SECTION_ALIASES.values() for alias in aliases}
    best = ""
    for node in nodes:
        for key in ("text", "description", "summary", "about"):
            candidate = _as_text(node.get(key))
            if not candidate or candidate.strip().lower() in section_titles:
                continue
            if len(candidate) > len(best):
                best = candidate
    return best
