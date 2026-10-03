from pathlib import Path

import pytest

from hr_parser import ParseError, parse_resume
from hr_parser.llm_client import DemoLLM
from hr_parser.pipeline import extract_json_text

SAMPLE = (Path(__file__).parent.parent / "sample" / "sample_resume.txt").read_text(encoding="utf-8")

EXPECTED = {  # the lab's expected output
    "full_name": "John Smith",
    "email": "john.smith@email.com",
    "education": [{"degree": "B.Sc. Computer Science", "institution": "MIT", "year": 2020}],
    "skills": ["Python", "Machine Learning", "Data Analysis"],
    "experience": [
        {"role": "Software Engineer", "company": "Google", "years": "2020–2023"},
        {"role": "Data Scientist", "company": "OpenAI", "years": "2023–Present"},
    ],
}


class ScriptedLLM:
    """Returns the given replies one after another."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), 0

    def generate(self, prompt, max_new_tokens=900):
        self.calls += 1
        return self.replies.pop(0)


def test_lab_sample_matches_expected_output():
    assert parse_resume(SAMPLE, DemoLLM()) == EXPECTED


def test_last_fenced_block_wins_and_plain_json_is_accepted():
    assert extract_json_text('```json\n{"a": 1}\n```\ntext ```json\n{"b": 2}\n```') == '{"b": 2}'
    assert extract_json_text('Sure! {"a": 1} done') == '{"a": 1}'


def test_missing_fields_are_tolerated():
    profile = parse_resume("x", ScriptedLLM('{"full_name": "Sam"}'))
    assert profile["full_name"] == "Sam" and profile["skills"] == []


def test_retry_after_broken_json():
    llm = ScriptedLLM("not json at all", '{"full_name": "Sam", "email": "s@x.io"}')
    assert parse_resume("x", llm)["email"] == "s@x.io"
    assert llm.calls == 2


def test_gives_up_with_a_friendly_error():
    with pytest.raises(ParseError):
        parse_resume("x", ScriptedLLM("nope", "still nope"))


def test_empty_resume_is_rejected():
    with pytest.raises(ParseError):
        parse_resume("   ", DemoLLM())
