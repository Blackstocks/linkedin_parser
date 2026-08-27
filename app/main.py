from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.errors import AppError, IncompleteSessionError, MissingCredentialsError
from app.linkedin.client import LinkedInClient
from app.models import ErrorBody, ErrorResponse, ProfileRequest, ProfileResponse
from app.urls import extract_vanity_name

logger = logging.getLogger(__name__)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.linkedin_client = LinkedInClient(settings)
    logger.info("Service started; LinkedIn session configured=%s", settings.has_session())
    try:
        yield
    finally:
        await app.state.linkedin_client.aclose()


STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="LinkedIn Profile Service",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=exc.code, message=exc.message))
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


@app.exception_handler(Exception)
async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    body = ErrorResponse(
        error=ErrorBody(code="internal_error", message="An unexpected error occurred")
    )
    return JSONResponse(status_code=500, content=body.model_dump())


@app.get("/docs", include_in_schema=False)
async def swagger_ui() -> HTMLResponse:
    spec = json.dumps(jsonable_encoder(app.openapi())).replace("<", "\\u003c").replace(">", "\\u003e")
    return HTMLResponse(
        f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{app.title}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({{
      spec: {spec},
      dom_id: "#swagger-ui",
      presets: [SwaggerUIBundle.presets.apis]
    }});
  </script>
</body>
</html>"""
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request) -> dict[str, bool]:
    return {"session_configured": bool(request.app.state.settings.has_session())}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/profile", response_model=ProfileResponse)
async def read_profile(payload: ProfileRequest, request: Request) -> ProfileResponse:
    settings: Settings = request.app.state.settings
    if bool(payload.li_at) != bool(payload.jsessionid):
        raise IncompleteSessionError()

    vanity_name = extract_vanity_name(str(payload.linkedin_url))
    logger.info(
        "Profile request vanity=%s session_source=%s",
        vanity_name,
        "request" if payload.li_at else "env",
    )

    if payload.li_at and payload.jsessionid:
        session_settings = settings.model_copy(
            update={
                "linkedin_li_at": payload.li_at,
                "linkedin_jsessionid": payload.jsessionid,
                "linkedin_csrf_token": "",
            }
        )
        client = LinkedInClient(session_settings)
        try:
            profile = await client.fetch_profile(vanity_name)
        finally:
            await client.aclose()
        return ProfileResponse(profile=profile)

    if not settings.has_session():
        raise MissingCredentialsError()

    client = request.app.state.linkedin_client
    profile = await client.fetch_profile(vanity_name)
    return ProfileResponse(profile=profile)
