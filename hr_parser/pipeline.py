"""resume text -> LLM -> JSON -> LangChain StructuredOutputParser -> normalised profile."""
from __future__ import annotations

import json
import re

from langchain_core.exceptions import OutputParserException

from .errors import ParseError
from .llm_client import LLM
from .prompts import build_prompt
from .schemas import FIELD_NAMES, normalize_profile, output_parser

MAX_RESUME_CHARS = 12_000  # keeps the prompt inside the model's comfortable context
RETRY_NOTE = "\n\nYour previous answer was not valid JSON. Return only the JSON object."


def extract_json_text(response: str) -> str:
    """Pick the JSON object out of a model response (fenced block first, braces second)."""
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    if fenced:
        return fenced[-1]
    start, end = response.find("{"), response.rfind("}")
    if start == -1 or end <= start:
        raise ParseError("The model did not return JSON.")
    return response[start : end + 1]


def parse_response(response: str) -> dict:
    """Validate a model response against the schema and normalise it."""
    try:
        data = json.loads(extract_json_text(response))
    except json.JSONDecodeError as exc:
        raise ParseError("The model returned broken JSON.") from exc
    if not isinstance(data, dict):
        raise ParseError("The model returned JSON in the wrong shape.")
    for name in FIELD_NAMES:  # tolerate omitted fields instead of failing the whole parse
        data.setdefault(name, [] if name in ("education", "skills", "experience") else "")
    try:
        parsed = output_parser.parse("```json\n" + json.dumps(data) + "\n```")
    except OutputParserException as exc:
        raise ParseError("The model output did not match the expected schema.") from exc
    return normalize_profile(parsed)


def parse_resume(cv_text: str, llm: LLM, retries: int = 1) -> dict:
    """Parse resume text into {full_name, email, education, skills, experience}."""
    if not cv_text or not cv_text.strip():
        raise ParseError("The resume is empty. Paste some text or upload a PDF.")
    prompt = build_prompt(cv_text.strip()[:MAX_RESUME_CHARS])
    error: ParseError | None = None
    for _ in range(retries + 1):
        try:
            return parse_response(llm.generate(prompt))
        except ParseError as exc:
            error = exc
            prompt += RETRY_NOTE
    raise ParseError(f"{error} Try again, or shorten the resume text.")
