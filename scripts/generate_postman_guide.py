#!/usr/bin/env python3
"""Generate docs/Postman-API-Testing-Guide.pdf"""

from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parents[1] / "docs" / "Postman-API-Testing-Guide.pdf"


class GuidePDF(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 8, "LinkedIn Profile Service  |  Postman API testing", align="L")
        self.ln(10)
        self.set_text_color(0, 0, 0)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}  |  Local base URL http://127.0.0.1:8000", align="C")
        self.set_text_color(0, 0, 0)

    def h1(self, text: str) -> None:
        self.set_font("Helvetica", "B", 20)
        self.multi_cell(0, 9, text)
        self.ln(2)

    def h2(self, text: str) -> None:
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.multi_cell(0, 7, text)
        self.ln(1)

    def h3(self, text: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.multi_cell(0, 6, text)
        self.ln(0.5)

    def body(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.2, text)
        self.ln(1)

    def bullet(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        x = self.get_x()
        self.cell(6, 5.2, "-")
        self.multi_cell(0, 5.2, text)
        self.set_x(x)

    def code(self, text: str) -> None:
        self.set_fill_color(245, 245, 245)
        self.set_font("Courier", "", 8.5)
        self.multi_cell(0, 4.6, text, fill=True)
        self.ln(2)

    def table(self, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
        self.set_font("Helvetica", "B", 8.5)
        self.set_fill_color(15, 102, 194)
        self.set_text_color(255, 255, 255)
        for h, w in zip(headers, widths, strict=True):
            self.cell(w, 7, h, border=1, fill=True)
        self.ln()
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 8)
        fill = False
        for row in rows:
            self.set_fill_color(248, 250, 252) if fill else self.set_fill_color(255, 255, 255)
            y0 = self.get_y()
            x0 = self.get_x()
            heights = []
            for value, w in zip(row, widths, strict=True):
                # estimate height
                lines = self.multi_cell(w, 4.5, value, dry_run=True, output="LINES")
                heights.append(4.5 * max(1, len(lines)))
            h = max(heights)
            if y0 + h > self.page_break_trigger:
                self.add_page()
                y0 = self.get_y()
                x0 = self.get_x()
            for value, w in zip(row, widths, strict=True):
                self.set_xy(x0, y0)
                self.multi_cell(w, 4.5, value, border=1, fill=True)
                x0 += w
            self.set_y(y0 + h)
            fill = not fill
        self.ln(2)


def build() -> None:
    pdf = GuidePDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(10, 102, 194)
    pdf.cell(0, 6, "HIRING CHALLENGE  |  LOCAL SERVICE")
    pdf.ln(8)
    pdf.set_text_color(0, 0, 0)
    pdf.h1("Postman API testing guide")
    pdf.body(
        "This document describes how to test the LinkedIn Profile Service in Postman. "
        "The service runs on your machine. LinkedIn session cookies stay in the server .env file; "
        "Postman does not send li_at. Never put cookies or tokens in this guide or in a shared collection."
    )

    pdf.h2("1. Prerequisites")
    pdf.bullet("Python venv activated in the project folder.")
    pdf.bullet(".env saved with LINKEDIN_LI_AT and LINKEDIN_JSESSIONID (plus bcookie and lidc in LINKEDIN_EXTRA_COOKIES when LinkedIn returns 401).")
    pdf.bullet("Server running: uvicorn app.main:app --host 127.0.0.1 --port 8000")
    pdf.bullet("Postman desktop or web (desktop is easier for localhost).")
    pdf.body("Confirm the process is up: open http://127.0.0.1:8000 in a browser, or run the Health request below.")

    pdf.h2("2. Postman setup (once)")
    pdf.h3("Create a collection")
    pdf.bullet("New -> Collection -> name it LinkedIn Profile Service.")
    pdf.h3("Collection variable")
    pdf.bullet("Collection -> Variables.")
    pdf.bullet("Add base_url = http://127.0.0.1:8000 (current value and initial value).")
    pdf.bullet("Use {{base_url}} in every request URL.")
    pdf.h3("No auth tab on the collection")
    pdf.body(
        "Do not add Bearer tokens or LinkedIn cookies in Postman. Authentication to LinkedIn happens "
        "inside the backend from .env. After you change .env, restart uvicorn before retesting."
    )

    pdf.h2("3. Endpoints")
    pdf.table(
        ["Method", "Path", "Auth to this API", "Purpose"],
        [
            ["GET", "/", "None", "HTML test UI (not required in Postman)"],
            ["GET", "/health", "None", "Process is running"],
            ["GET", "/ready", "None", "True if .env session cookies loaded"],
            ["POST", "/profile", "None (server uses .env)", "Fetch and normalize a LinkedIn profile"],
        ],
        [22, 28, 48, 72],
    )

    pdf.h2("4. Request: GET Health")
    pdf.body("Checks that uvicorn is listening. Does not call LinkedIn.")
    pdf.code("GET {{base_url}}/health")
    pdf.body("Postman: New request -> GET -> {{base_url}}/health -> Send. No body, no headers required.")
    pdf.h3("Expected")
    pdf.code('HTTP 200\n{\n  "status": "ok"\n}')
    pdf.body("If connection refused: the server is not running or the port is not 8000.")

    pdf.h2("5. Request: GET Ready")
    pdf.body("Checks whether LINKEDIN_LI_AT and LINKEDIN_JSESSIONID were loaded at process start.")
    pdf.code("GET {{base_url}}/ready")
    pdf.h3("Expected when .env is loaded and uvicorn was started after saving .env")
    pdf.code('HTTP 200\n{\n  "session_configured": true\n}')
    pdf.h3("Expected when cookies are missing")
    pdf.code('HTTP 200\n{\n  "session_configured": false\n}')
    pdf.body("session_configured false with a saved .env usually means uvicorn was not restarted after the file change.")

    pdf.add_page()
    pdf.h2("6. Request: POST Profile (primary test)")
    pdf.body("This is the challenge endpoint. Postman sends only a public LinkedIn profile URL.")
    pdf.code("POST {{base_url}}/profile")
    pdf.h3("Headers")
    pdf.table(
        ["Header", "Value"],
        [["Content-Type", "application/json"]],
        [50, 120],
    )
    pdf.h3("Body (raw JSON)")
    pdf.code('{\n  "linkedin_url": "https://www.linkedin.com/in/username/"\n}')
    pdf.body(
        "Replace username with a real vanity slug. Query strings are allowed "
        "(?trk=...). Company pages and other hosts are rejected."
    )
    pdf.h3("Postman clicks")
    pdf.bullet("Method POST, URL {{base_url}}/profile")
    pdf.bullet("Headers: Content-Type = application/json (Body -> raw -> JSON also sets this).")
    pdf.bullet("Body -> raw -> JSON -> paste the object above.")
    pdf.bullet("Send. First LinkedIn round-trip can take a few seconds.")

    pdf.h3("Expected success (HTTP 200)")
    pdf.code(
        '{\n'
        '  "profile": {\n'
        '    "name": "string",\n'
        '    "headline": "string",\n'
        '    "location": "string",\n'
        '    "about": "string",\n'
        '    "image_url": "string",\n'
        '    "experience": [\n'
        '      {\n'
        '        "title": "string",\n'
        '        "company": "string",\n'
        '        "location": "string",\n'
        '        "dates": "string",\n'
        '        "description": "string"\n'
        '      }\n'
        '    ],\n'
        '    "education": [\n'
        '      {\n'
        '        "school": "string",\n'
        '        "degree": "string",\n'
        '        "field": "string",\n'
        '        "dates": "string"\n'
        '      }\n'
        '    ],\n'
        '    "skills": ["string"],\n'
        '    "certifications": [\n'
        '      { "name": "string", "issuer": "string", "date": "string" }\n'
        '    ],\n'
        '    "languages": [\n'
        '      { "name": "string", "proficiency": "string" }\n'
        '    ]\n'
        '  }\n'
        '}'
    )
    pdf.body(
        "Empty strings and empty arrays are valid when LinkedIn did not return that section "
        "(certifications and languages are often empty). Tests should assert HTTP 200, "
        "a profile object, and name or headline populated for a known public profile."
    )

    pdf.h2("7. Negative tests (Postman)")
    pdf.table(
        ["Case", "Body / URL", "HTTP", "error.code"],
        [
            [
                "Invalid URL (company page)",
                '{"linkedin_url":"https://www.linkedin.com/company/example/"}',
                "400",
                "invalid_linkedin_url",
            ],
            [
                "Malformed JSON / missing field",
                "{}",
                "422",
                "(FastAPI validation; detail array, not error.code)",
            ],
            [
                "linkedin_url not a URL",
                '{"linkedin_url":"not-a-url"}',
                "422",
                "(validation)",
            ],
            [
                "Session expired / LinkedIn 302",
                "valid profile URL",
                "401",
                "linkedin_auth_failed",
            ],
            [
                "Profile cannot be resolved",
                "valid shape, unknown slug",
                "404",
                "profile_not_found",
            ],
            [
                "LinkedIn 429",
                "valid profile URL",
                "429",
                "linkedin_upstream_error",
            ],
            [
                ".env cookies missing at startup",
                "valid profile URL",
                "500",
                "missing_credentials",
            ],
            [
                "LinkedIn 999 / other failure",
                "valid profile URL",
                "502",
                "linkedin_upstream_error",
            ],
        ],
        [38, 72, 18, 42],
    )
    pdf.body("Error envelope (except FastAPI 422):")
    pdf.code('{\n  "error": {\n    "code": "linkedin_auth_failed",\n    "message": "human readable text"\n  }\n}')

    pdf.h2("8. Tests tab (optional Postman scripts)")
    pdf.body("On POST /profile, Tests tab example:")
    pdf.code(
        "pm.test('status is 200', function () {\n"
        "  pm.response.to.have.status(200);\n"
        "});\n"
        "pm.test('profile has name', function () {\n"
        "  const json = pm.response.json();\n"
        "  pm.expect(json.profile).to.be.an('object');\n"
        "  pm.expect(json.profile.name).to.be.a('string');\n"
        "  pm.expect(json.profile.experience).to.be.an('array');\n"
        "  pm.expect(json.profile.education).to.be.an('array');\n"
        "  pm.expect(json.profile.skills).to.be.an('array');\n"
        "});"
    )
    pdf.body("On GET /health:")
    pdf.code(
        "pm.test('healthy', function () {\n"
        "  pm.response.to.have.status(200);\n"
        "  pm.expect(pm.response.json().status).to.eql('ok');\n"
        "});"
    )

    pdf.add_page()
    pdf.h2("9. Collection runner")
    pdf.bullet("Save Health, Ready, Profile (success), Profile (invalid URL) as four requests.")
    pdf.bullet("Runner -> select those requests -> keep delay 0 for Health/Ready.")
    pdf.bullet("Do not loop POST /profile at high volume. LinkedIn will invalidate the session (401).")
    pdf.bullet("One live profile lookup per run is enough for a demo.")

    pdf.h2("10. Import as cURL (alternative to clicking)")
    pdf.body("Postman: Import -> Raw text -> paste:")
    pdf.code(
        "curl --request GET 'http://127.0.0.1:8000/health'"
    )
    pdf.code(
        "curl --request GET 'http://127.0.0.1:8000/ready'"
    )
    pdf.code(
        "curl --request POST 'http://127.0.0.1:8000/profile' \\\n"
        "  --header 'Content-Type: application/json' \\\n"
        "  --data '{\"linkedin_url\":\"https://www.linkedin.com/in/username/\"}'"
    )
    pdf.body("Then replace username and save into the collection.")

    pdf.h2("11. Troubleshooting")
    pdf.table(
        ["Symptom", "What to do"],
        [
            [
                "Could not send request / ECONNREFUSED",
                "Start uvicorn on 127.0.0.1:8000. In Postman web, localhost may be blocked; use the desktop app.",
            ],
            [
                "304 on browser static files; Postman still old?",
                "Postman does not cache this API. Unrelated. Hit Send again.",
            ],
            [
                "session_configured false",
                "Save .env, stop uvicorn (Ctrl+C), start it again.",
            ],
            [
                "401 linkedin_auth_failed",
                "Refresh li_at, JSESSIONID, bcookie, lidc from Chrome; save .env; restart uvicorn.",
            ],
            [
                "422 on POST /profile",
                "Body must be raw JSON with linkedin_url as a full https URL, not form-data.",
            ],
            [
                "200 but empty name and empty lists",
                "Unusual; treat as a failed parse. Retry once. If it persists, the LinkedIn payload shape changed.",
            ],
        ],
        [55, 115],
    )

    pdf.h2("12. Security notes for testers")
    pdf.bullet("Do not put LINKEDIN_LI_AT in Postman environment variables or screenshots.")
    pdf.bullet("Do not export a collection that contains real profile PII to a public gist.")
    pdf.bullet("Do not commit .env.")

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(
        0,
        5,
        "Document generated for local Postman testing of this repository. "
        "Interactive OpenAPI UI is also at http://127.0.0.1:8000/docs",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
