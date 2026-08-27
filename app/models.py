from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ExperienceItem(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    dates: str = ""
    description: str = ""


class EducationItem(BaseModel):
    school: str = ""
    degree: str = ""
    field: str = ""
    dates: str = ""


class CertificationItem(BaseModel):
    name: str = ""
    issuer: str = ""
    date: str = ""


class LanguageItem(BaseModel):
    name: str = ""
    proficiency: str = ""


class Profile(BaseModel):
    name: str = ""
    headline: str = ""
    location: str = ""
    about: str = ""
    image_url: str = ""
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)


class ProfileRequest(BaseModel):
    linkedin_url: HttpUrl
    li_at: str = ""
    jsessionid: str = ""

    @field_validator("li_at", "jsessionid", mode="before")
    @classmethod
    def strip_session_quotes(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value


class ProfileResponse(BaseModel):
    profile: Profile


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
