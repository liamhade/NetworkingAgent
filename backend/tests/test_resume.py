import pytest
from pdf_utils import make_pdf

import resume
from schemas import ResumeProfile


def test_extract_pdf_text() -> None:
    text = resume.extract_pdf_text(make_pdf(["Jane Doe", "Data Analyst at Acme (2021-2024)"]))
    assert "Jane Doe" in text
    assert "Data Analyst at Acme" in text


def test_extract_rejects_non_pdf() -> None:
    with pytest.raises(resume.ResumeError):
        resume.extract_pdf_text(b"not a pdf")


def test_extract_rejects_empty_pdf() -> None:
    with pytest.raises(resume.ResumeError):
        resume.extract_pdf_text(make_pdf([]))


def test_parse_resume_uses_json_schema_structured_output(scripted_model) -> None:
    profile = ResumeProfile(background="I am an analyst.", location="Brooklyn, NY", looking_for="")
    model = scripted_model(structured=profile)
    assert resume.parse_resume(make_pdf(["Jane Doe", "Analyst"]), llm=model) == profile
    call = model.structured_calls[0]
    assert call["schema"] is ResumeProfile
    assert call["kwargs"] == {"method": "json_schema"}
    assert "Jane Doe" in call["input"][1].content


def test_parse_resume_accepts_dict_output(scripted_model) -> None:
    model = scripted_model(
        structured={"background": "I build things.", "location": "", "looking_for": "SWE"}
    )
    assert resume.parse_resume(make_pdf(["x"]), llm=model).looking_for == "SWE"


def test_resume_profile_education_is_required_for_the_llm_but_defaults_for_saved_ones() -> None:
    from schemas import ResumeProfile

    assert "education" in ResumeProfile.model_json_schema()["required"]
    old = ResumeProfile.model_validate({"background": "b", "location": "", "looking_for": ""})
    assert old.education == []
