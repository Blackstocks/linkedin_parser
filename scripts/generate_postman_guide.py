#!/usr/bin/env python3

from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parents[1] / "docs" / "Postman-API-Testing-Guide.pdf"

LEFT = 18
CONTENT = 174


class PDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 8, str(self.page_no()), align="C")

    def title_line(self, text: str) -> None:
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(20, 20, 20)
        self.multi_cell(CONTENT, 8, text)
        self.ln(4)

    def section(self, text: str) -> None:
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(10, 102, 194)
        self.cell(CONTENT, 7, text)
        self.ln(8)
        self.set_text_color(30, 30, 30)

    def p(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(CONTENT, 5.5, text)
        self.ln(2)

    def step(self, n: int, text: str) -> None:
        self.set_font("Helvetica", "B", 10)
        self.cell(8, 5.5, f"{n}.")
        self.set_font("Helvetica", "", 10)
        self.multi_cell(CONTENT - 8, 5.5, text)
        self.ln(1)

    def code(self, text: str) -> None:
        self.set_fill_color(245, 246, 248)
        self.set_font("Courier", "", 8)
        self.set_text_color(20, 20, 20)
        self.multi_cell(CONTENT, 4.4, text, fill=True)
        self.ln(3)

    def kv_row(self, left: str, right: str, y_pad: float = 6.5) -> None:
        x = self.l_margin
        y = self.get_y()
        self.set_fill_color(248, 249, 251)
        self.rect(x, y, 48, y_pad, "F")
        self.set_xy(x + 1.5, y + 0.8)
        self.set_font("Helvetica", "B", 9)
        self.cell(45, 5, left)
        self.set_xy(x + 50, y + 0.8)
        self.set_font("Helvetica", "", 9)
        self.multi_cell(CONTENT - 50, 5, right)
        h = max(y_pad, self.get_y() - y)
        self.set_y(y + h + 1)


def build() -> None:
    pdf = PDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_left_margin(LEFT)
    pdf.set_right_margin(LEFT)
    pdf.add_page()

    pdf.title_line("Postman: test POST /profile")
    pdf.p(
        "One request. Send the profile URL plus your own LinkedIn cookies in the JSON body. "
        "Do not use Postman Auth, Bearer tokens, or a Cookie header."
    )

    pdf.section("Base URL")
    pdf.kv_row("Live", "https://linkedin-parser-s5wh.onrender.com")
    pdf.kv_row("Local", "http://127.0.0.1:8000")

    pdf.section("Where to get li_at and JSESSIONID")
    pdf.step(1, "Sign in to https://www.linkedin.com in Chrome (your account).")
    pdf.step(2, "DevTools: Cmd+Option+I (Mac) or F12 (Windows).")
    pdf.step(3, "Application > Cookies > https://www.linkedin.com")
    pdf.step(4, "Copy Value for li_at (starts with AQED).")
    pdf.step(5, "Copy Value for JSESSIONID (looks like ajax:...). Same table, same time.")
    pdf.p("Both cookies must come from that one session. Quotes around the value are optional.")

    pdf.section("Postman setup")
    pdf.step(1, "New request. Method: POST.")
    pdf.step(2, "URL: {{base}}/profile   (set collection variable base to the live or local URL).")
    pdf.step(3, "Authorization tab: No Auth.")
    pdf.step(4, "Headers: Content-Type = application/json")
    pdf.step(5, "Body > raw > JSON. Paste:")
    pdf.code(
        '{\n'
        '  "linkedin_url": "https://www.linkedin.com/in/username/",\n'
        '  "li_at": "PASTE_LI_AT_VALUE",\n'
        '  "jsessionid": "PASTE_JSESSIONID_VALUE"\n'
        "}"
    )
    pdf.step(6, "Replace username, PASTE_LI_AT_VALUE, and PASTE_JSESSIONID_VALUE. Click Send.")

    pdf.section("Optional: GET /health")
    pdf.p("GET {{base}}/health   no body. Expect 200 and {\"status\":\"ok\"}. Use this to see if Render is awake.")

    pdf.add_page()
    pdf.section("Success (200)")
    pdf.p("JSON object with key profile, then: name, headline, location, about, image_url, experience[], education[], skills[], certifications[], languages[]. Empty strings or empty arrays mean LinkedIn did not return that field.")

    pdf.section("If it fails")
    pdf.kv_row("400", "Bad URL, or only one of li_at / jsessionid sent.")
    pdf.kv_row("401", "Cookies expired or mixed from two sessions. Copy both again.")
    pdf.kv_row("422", "Body is not JSON, or linkedin_url is not a full https URL.")
    pdf.kv_row("502", "LinkedIn rejected the upstream call. Wait and retry with fresh cookies.")
    pdf.p("Error shape: {\"error\":{\"code\":\"...\",\"message\":\"...\"}}")

    pdf.section("Do not")
    pdf.p(
        "Do not put li_at in Postman Authorization. Do not mix cookies from two browsers. "
        "Do not hammer Send; LinkedIn will invalidate the session."
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
