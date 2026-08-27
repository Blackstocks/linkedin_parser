from __future__ import annotations


class AppError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class InvalidLinkedInUrlError(AppError):
    def __init__(self, message: str = "linkedin_url must be a LinkedIn profile URL") -> None:
        super().__init__(message, code="invalid_linkedin_url", status_code=400)


class IncompleteSessionError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "Provide both li_at and JSESSIONID from the same LinkedIn Chrome session.",
            code="incomplete_session",
            status_code=400,
        )


class MissingCredentialsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "LinkedIn session cookies are not configured. Set LINKEDIN_LI_AT and LINKEDIN_JSESSIONID.",
            code="missing_credentials",
            status_code=500,
        )


class LinkedInAuthError(AppError):
    def __init__(self, message: str = "LinkedIn session is missing or expired") -> None:
        super().__init__(message, code="linkedin_auth_failed", status_code=401)


class LinkedInUpstreamError(AppError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message, code="linkedin_upstream_error", status_code=status_code)


class ProfileNotFoundError(AppError):
    def __init__(self, vanity_name: str) -> None:
        super().__init__(
            f"LinkedIn profile not found for vanity name '{vanity_name}'",
            code="profile_not_found",
            status_code=404,
        )
