from __future__ import annotations

from pathlib import Path

from app.envfile import upsert_env


def test_upsert_env_replaces_and_preserves(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("LOG_LEVEL=INFO\nLINKEDIN_LI_AT=old\nSITE_ADDRESS=localhost\n", encoding="utf-8")
    upsert_env(path, {"LINKEDIN_LI_AT": "new-token", "LINKEDIN_JSESSIONID": "ajax:1"})
    text = path.read_text(encoding="utf-8")
    assert "LOG_LEVEL=INFO" in text
    assert "SITE_ADDRESS=localhost" in text
    assert "LINKEDIN_LI_AT=new-token" in text
    assert "LINKEDIN_JSESSIONID=ajax:1" in text
    assert "old" not in text
