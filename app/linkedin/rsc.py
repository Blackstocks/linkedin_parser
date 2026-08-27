from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_FLIGHT_LINE = re.compile(r"^(?:[A-Za-z])?(?P<id>\d+):(?P<body>.*)$")


def decode_rsc_payload(raw: str) -> Any:
    """Decode LinkedIn's RSC/SDUI wire format into JSON-compatible Python values.

    The flagship-web component endpoint is not a single JSON document. Observed
    shapes include:

    * a JSON object or array
    * React Flight / RSC lines (`0:{...}`, `1:[...]`)
    * a stream of concatenated JSON values
    """
    text = (raw or "").lstrip("\ufeff").strip()
    if not text:
        return {}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    chunks = _parse_flight_stream(text)
    if chunks:
        return chunks if len(chunks) > 1 else chunks[0]

    concatenated = _parse_concatenated_json(text)
    if concatenated:
        return concatenated if len(concatenated) > 1 else concatenated[0]

    logger.warning("RSC payload was not JSON or Flight; returning raw text wrapper")
    return {"_raw": text}


def _parse_flight_stream(text: str) -> list[Any]:
    values: list[Any] = []
    matched_any = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _FLIGHT_LINE.match(stripped)
        if not match:
            if matched_any:
                continue
            return []
        matched_any = True
        body = match.group("body").strip()
        if body in {"", "null"}:
            continue
        try:
            values.append(json.loads(body))
        except json.JSONDecodeError:
            logger.debug("Skipping non-JSON RSC flight chunk")
            continue
    return values


def _parse_concatenated_json(text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    values: list[Any] = []
    idx = 0
    length = len(text)
    while idx < length:
        while idx < length and text[idx].isspace():
            idx += 1
        if idx >= length:
            break
        try:
            value, offset = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            return []
        values.append(value)
        idx = offset
    return values
