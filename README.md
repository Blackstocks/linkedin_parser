# LinkedIn Profile Service

Backend for a hiring challenge that **replays your own authenticated LinkedIn browser session** and returns a profile as structured JSON.

It does not log in for you, solve CAPTCHA, bypass rate limits, or evade bot checks. You copy cookies from a session you already established in Chrome and supply them through environment variables.

## How the captured request maps to this service

In DevTools you identified:

```
POST https://www.linkedin.com/flagship-web/rsc-action/actions/component
     ?componentId=com.linkedin.sdui.generated.profile.dsl.impl.profileCardsAboveActivity
```

That call is LinkedIn flagship-web **SDUI** (server-driven UI). The body is protobuf-JSON, not a public REST resource. The response is an **RSC/SDUI stream**, not a stable profile JSON schema.

| Browser request | Backend |
| --- | --- |
| Profile URL `/in/{vanity}/` | `POST /profile` `{ "linkedin_url": "..." }` → extract vanity name |
| Cookie `li_at` | `LINKEDIN_LI_AT` |
| Cookie `JSESSIONID` | `LINKEDIN_JSESSIONID` |
| Header `csrf-token` (JSESSIONID without quotes) | Derived in `LinkedInClient` |
| Body `vanityName` | Parsed from `linkedin_url` |
| Body `vieweeProfileId` | Resolved with the same session via identity dash (the mapping the profile page uses), with an HTML URN fallback |
| Body `isSelfView` | `false` |
| Body `profileComponentState` | `{}` |
| RSC/SDUI response | `app/linkedin/rsc.py` decodes the wire format, `app/linkedin/parser.py` walks the component tree |

```
Client                  This API                     LinkedIn (your session)
  |                        |                                |
  | POST /profile          |                                |
  | {linkedin_url}         |                                |
  |----------------------->| extract vanity                 |
  |                        | GET /voyager/api/identity/...  |
  |                        |------------------------------->|
  |                        | vieweeProfileId                |
  |                        | POST /flagship-web/rsc-action/ |
  |                        |      actions/component         |
  |                        |------------------------------->|
  |                        | RSC / SDUI payload             |
  |                        | parse + Pydantic normalize     |
  | { profile: {...} }     |                                |
  |<-----------------------|                                |
```

`profileCardsAboveActivity` is the card stack **above the activity feed** (intro, about, and typically experience / education / skills when LinkedIn places them there). If a live response omits a section, the API still returns the field as an empty string or empty list.

## API

`POST /profile`

```json
{
  "linkedin_url": "https://www.linkedin.com/in/username/"
}
```

```json
{
  "profile": {
    "name": "",
    "headline": "",
    "location": "",
    "about": "",
    "image_url": "",
    "experience": [],
    "education": [],
    "skills": [],
    "certifications": [],
    "languages": []
  }
}
```

`GET /health` — liveness for Docker / load balancers.

## Credentials (never commit these)

1. Sign in to LinkedIn in Chrome as yourself.
2. DevTools → Application → Cookies → `https://www.linkedin.com`.
3. Copy `li_at` and `JSESSIONID`.
4. `cp .env.example .env` and paste the values.

Optional: copy extra request headers from the captured component call into `LINKEDIN_EXTRA_HEADERS` (JSON object) if LinkedIn starts requiring page-instance headers such as `x-li-page-instance`. Do not put cookies in that JSON.

Treat `li_at` like a password. Rotate it if it leaks.

There is **no long-lived unofficial token**. `li_at` is a browser session cookie. LinkedIn expires, rotates, or challenges it after Voyager calls. Official LinkedIn OAuth APIs do not replace this: they generally cannot fetch arbitrary member profiles the way this challenge does.

What you can do instead of pasting from DevTools every time:

1. Stay signed in in a dedicated Chrome profile.
2. Pull cookies from that Chrome into `.env`:

```bash
# Quit Chrome first, then:
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --remote-allow-origins=* \
  --user-data-dir="$HOME/.linkedin-chrome-profile"

# Sign in at https://www.linkedin.com/feed/ in that window, then:
pip install -e ".[dev]"
python scripts/sync_chrome_cookies.py
```

Restart uvicorn after the script runs. This still uses **your** session; it does not log in for you or keep LinkedIn from invalidating the cookie.

## Local run

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# edit .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and paste a profile URL. The page calls `POST /profile` on the same origin.

```bash
curl -sS http://127.0.0.1:8000/profile \
  -H 'content-type: application/json' \
  -d '{"linkedin_url":"https://www.linkedin.com/in/username/"}'
```

## Tests

Parser tests use **anonymized fixtures** under `tests/fixtures/` (no live LinkedIn calls):

```bash
pytest -q
```

To refine the parser against a real capture, save the component response body to `tests/fixtures/` with personal data removed, then add an assertion in `tests/test_parser.py`. Do not commit raw captures that contain your session or other people's PII.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

The `api` container serves HTTP on the internal network. **Caddy** terminates HTTPS on ports 80 and 443.

### HTTPS deployment

Set the public hostname and start Compose:

```bash
export SITE_ADDRESS=profile.example.com
docker compose up --build -d
```

Caddy requests a Let's Encrypt certificate for `SITE_ADDRESS` when the hostname is a real domain pointing at the host. For local TLS, `SITE_ADDRESS=localhost` uses Caddy's local HTTPS.

Point DNS A/AAAA records at the server before the first start. Open ports 80 and 443.

If you prefer nginx, use `deploy/nginx.conf.example` and mount certificates from `certs/` (gitignored).

Uvicorn is started with `--proxy-headers` so `X-Forwarded-Proto` from Caddy/nginx is trusted behind the reverse proxy.

## Project layout

- `app/main.py` — FastAPI routes and error handling
- `app/urls.py` — vanity name extraction
- `app/linkedin/client.py` — authenticated LinkedIn HTTP client
- `app/linkedin/rsc.py` — RSC / Flight / concatenated-JSON decoder
- `app/linkedin/parser.py` — SDUI tree → `Profile`
- `app/models.py` — Pydantic models
- `tests/fixtures/` — saved response fixtures
- `deploy/` — Caddy and nginx TLS configs

## Errors

| HTTP | Code | Meaning |
| --- | --- | --- |
| 400 | `invalid_linkedin_url` | URL is not `/in/{vanity}/` |
| 401 | `linkedin_auth_failed` | Session cookie missing, expired, or rejected |
| 404 | `profile_not_found` | Vanity name could not be resolved |
| 429 | `linkedin_upstream_error` | LinkedIn rate-limited the session (not retried in a loop) |
| 500 | `missing_credentials` | Env vars not set |
| 502 | `linkedin_upstream_error` | Other LinkedIn HTTP failure |

## Scope

Permitted here: using **your** session cookies, reproducing the component request you already make in the browser, parsing the response.

Out of scope: CAPTCHA solving, auth bypass, authorization bypass, credential theft, TLS fingerprint spoofing, or rate-limit evasion.
