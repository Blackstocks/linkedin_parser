#!/usr/bin/env python3
"""Copy LinkedIn cookies from a Chrome instance you already logged into.

This does not log in, solve CAPTCHA, or keep a session alive forever.
It only reads cookies from Chrome DevTools (port 9222) into .env.

1. Quit Chrome completely.
2. Start Chrome with remote debugging, using a profile that is logged into LinkedIn:

   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
     --remote-debugging-port=9222 --remote-allow-origins=* \\
     --user-data-dir="$HOME/.linkedin-chrome-profile"

3. In that window, open https://www.linkedin.com/feed/ and confirm you are signed in.
4. python scripts/sync_chrome_cookies.py
5. Restart uvicorn so it reloads .env.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.envfile import upsert_env

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222
WANTED = {"li_at", "JSESSIONID", "bcookie", "bscookie", "lidc", "liap"}


def _cdp_targets() -> list[dict]:
    url = f"http://{CDP_HOST}:{CDP_PORT}/json/list"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.loads(response.read().decode())
    except OSError as exc:
        raise SystemExit(
            "Could not reach Chrome on port 9222.\n"
            "Quit Chrome, start it with --remote-debugging-port=9222, "
            "open linkedin.com while signed in, then rerun this script."
        ) from exc


def _pick_websocket(targets: list[dict]) -> str:
    pages = [item for item in targets if item.get("type") == "page" and item.get("webSocketDebuggerUrl")]
    linkedin = [item for item in pages if "linkedin.com" in (item.get("url") or "")]
    chosen = (linkedin or pages)[0] if (linkedin or pages) else None
    if not chosen:
        raise SystemExit("Chrome is open, but there is no page tab. Open https://www.linkedin.com/feed/")
    return chosen["webSocketDebuggerUrl"]


def _get_cookies(ws_url: str) -> list[dict]:
    try:
        import websocket
    except ImportError as exc:
        raise SystemExit("pip install websocket-client") from exc

    conn = websocket.create_connection(ws_url, origin=f"http://{CDP_HOST}:{CDP_PORT}", timeout=10)
    try:
        conn.send(json.dumps({"id": 1, "method": "Network.getAllCookies"}))
        while True:
            message = json.loads(conn.recv())
            if message.get("id") == 1:
                return message.get("result", {}).get("cookies") or []
    finally:
        conn.close()


def _linkedin_cookies(raw: list[dict]) -> dict[str, str]:
    found: dict[str, str] = {}
    for cookie in raw:
        name = cookie.get("name") or ""
        domain = cookie.get("domain") or ""
        if name not in WANTED:
            continue
        if "linkedin" not in domain:
            continue
        found[name] = str(cookie.get("value") or "")
    return found


def main() -> None:
    cookies = _linkedin_cookies(_get_cookies(_pick_websocket(_cdp_targets())))
    li_at = cookies.get("li_at", "")
    jsession = cookies.get("JSESSIONID", "")
    if not li_at or not jsession:
        raise SystemExit(
            "Chrome did not have li_at and JSESSIONID for linkedin.com. "
            "Sign in at https://www.linkedin.com/feed/ in the debug Chrome window."
        )
    extra_parts = [
        f"{name}={cookies[name]}"
        for name in ("bcookie", "bscookie", "lidc", "liap")
        if cookies.get(name)
    ]
    env_path = ROOT / ".env"
    upsert_env(
        env_path,
        {
            "LINKEDIN_LI_AT": li_at,
            "LINKEDIN_JSESSIONID": jsession,
            "LINKEDIN_EXTRA_COOKIES": "; ".join(extra_parts),
        },
    )
    print(
        f"Updated {env_path} with li_at ({len(li_at)} chars), "
        f"JSESSIONID, and {len(extra_parts)} extra cookies."
    )
    print("Restart uvicorn so the process reloads .env.")


if __name__ == "__main__":
    main()
