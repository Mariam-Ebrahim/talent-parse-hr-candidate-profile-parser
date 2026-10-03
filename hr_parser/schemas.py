"""Output schema, normalisation and export helpers for candidate profiles."""
from __future__ import annotations

import re
from typing import Any

from langchain_classic.output_parsers import ResponseSchema, StructuredOutputParser

# The schema required by the lab task, expressed as LangChain response schemas.
RESPONSE_SCHEMAS = [
    ResponseSchema(name="full_name", description="Candidate's full name"),
    ResponseSchema(name="email", description="Candidate's email address"),
    ResponseSchema(
        name="education",
        description="List of objects with keys: degree, institution, year (year as an integer)",
        type="List[dict]",
    ),
    ResponseSchema(name="skills", description="List of skill strings", type="List[string]"),
    ResponseSchema(
        name="experience",
        description="List of objects with keys: role, company, years (years as a string like '2020-2023')",
        type="List[dict]",
    ),
]
output_parser = StructuredOutputParser.from_response_schemas(RESPONSE_SCHEMAS)
FORMAT_INSTRUCTIONS = output_parser.get_format_instructions()
FIELD_NAMES = [schema.name for schema in RESPONSE_SCHEMAS]

EN_DASH = "–"  # the lab's expected output writes "2020–2023" with an en dash
_YEARS_RE = re.compile(r"\d{4}|present|current|now", re.IGNORECASE)
_YEAR_RE = re.compile(r"\d{4}")
_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def new_profile() -> dict:
    return {"full_name": "", "email": "", "education": [], "skills": [], "experience": []}


def _text(value: Any) -> str:
    if value is None or (isinstance(value, float) and value != value):  # None or NaN
        return ""
    return str(value).strip()


def normalize_year(value: Any) -> int | None:
    """'2020', 2020 or 'May 2020' -> 2020; anything without a 4-digit year -> None."""
    match = _YEAR_RE.search(_text(value))
    return int(match.group()) if match else None


def normalize_years(value: Any) -> str:
    """'Jan 2020 - Mar 2023' -> '2020–2023'; 'since 2023 to now' -> '2023–Present'."""
    tokens = [t if t.isdigit() else "Present" for t in _YEARS_RE.findall(_text(value))]
    return EN_DASH.join(tokens[:2])


def _skill_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = re.split(r"[,;\n]", value)
    seen, skills = set(), []
    for item in value or []:
        skill = _text(item)
        if skill and skill.lower() not in seen:
            seen.add(skill.lower())
            skills.append(skill)
    return skills


def normalize_profile(raw: dict | None) -> dict:
    """Clean a raw profile (from the LLM or from the UI) into the final schema."""
    raw = raw or {}
    education = []
    for item in raw.get("education") or []:
        if not isinstance(item, dict):
            continue
        row = {
            "degree": _text(item.get("degree")),
            "institution": _text(item.get("institution")),
            "year": normalize_year(item.get("year")),
        }
        if row["degree"] or row["institution"]:
            education.append(row)

    experience = []
    for item in raw.get("experience") or []:
        if not isinstance(item, dict):
            continue
        row = {
            "role": _text(item.get("role")),
            "company": _text(item.get("company")),
            "years": normalize_years(item.get("years")) or _text(item.get("years")),
        }
        if row["role"] or row["company"]:
            experience.append(row)

    return {
        "full_name": _text(raw.get("full_name")),
        "email": _text(raw.get("email")),
        "education": education,
        "skills": _skill_list(raw.get("skills")),
        "experience": experience,
    }


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def count_filled(profile: dict) -> int:
    """Number of non-empty values, shown as 'N fields auto-filled' in the UI."""
    count = sum(1 for key in ("full_name", "email") if profile.get(key))
    for row in profile.get("education", []):
        count += sum(1 for value in row.values() if value not in ("", None))
    for row in profile.get("experience", []):
        count += sum(1 for value in row.values() if value not in ("", None))
    return count + len(profile.get("skills", []))
