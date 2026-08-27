from __future__ import annotations

from pathlib import Path


def upsert_env(path: Path, updates: dict[str, str]) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    written = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            out.append(f"{key}={_format_env_value(updates[key])}")
            written.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in written:
            out.append(f"{key}={_format_env_value(value)}")
    text = "\n".join(out).rstrip() + "\n"
    path.write_text(text, encoding="utf-8")


def _format_env_value(value: str) -> str:
    if any(ch in value for ch in ' \t#"\''):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value
