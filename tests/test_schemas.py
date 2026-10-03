from hr_parser.schemas import (count_filled, is_valid_email, normalize_profile, normalize_year,
                               normalize_years)


def test_years_drop_month_names_and_use_en_dash():
    assert normalize_years("Jan 2020 - Mar 2023") == "2020–2023"
    assert normalize_years("2023-Present") == "2023–Present"
    assert normalize_years("since 2021 to now") == "2021–Present"
    assert normalize_years("2020") == "2020"
    assert normalize_years("three years") == ""


def test_year_is_integer_or_none():
    assert normalize_year("2020") == 2020
    assert normalize_year(2020) == 2020
    assert normalize_year("May 2019") == 2019
    assert normalize_year("n/a") is None


def test_normalize_profile_cleans_and_fills_defaults():
    profile = normalize_profile({
        "full_name": "  Jane Doe ",
        "skills": "Python, SQL; python",
        "education": [{"degree": "BSc", "institution": "MIT", "year": "2020"}, "junk", {}],
        "experience": [{"role": "Dev", "company": "ACME", "years": "Jan 2020 - 2022"}],
    })
    assert profile["full_name"] == "Jane Doe"
    assert profile["email"] == ""
    assert profile["skills"] == ["Python", "SQL"]
    assert profile["education"] == [{"degree": "BSc", "institution": "MIT", "year": 2020}]
    assert profile["experience"][0]["years"] == "2020–2022"


def test_nan_cells_from_the_editor_become_empty():
    profile = normalize_profile({"education": [{"degree": "BSc", "institution": float("nan"), "year": None}]})
    assert profile["education"] == [{"degree": "BSc", "institution": "", "year": None}]


def test_email_check_and_filled_count():
    assert is_valid_email("john.smith@email.com")
    assert not is_valid_email("john.smith@")
    assert count_filled(normalize_profile({"full_name": "A", "skills": ["x", "y"]})) == 3
