import pytest
from pydantic import ValidationError

# Corrected import path if schemas.py is in app/schemas/
from app.schemas.schemas import BaseResponse, ResumeDataInput

class TestBaseResponse:
    def test_base_response_valid(self):
        data = {"message": "Success"}
        response = BaseResponse(**data)
        assert response.message == "Success"

    def test_base_response_missing_message(self):
        with pytest.raises(ValidationError) as excinfo:
            BaseResponse() # type: ignore
        assert "message" in str(excinfo.value)
        # For pydantic v2, errors are more structured
        # assert any(err['type'] == 'missing' and err['loc'] == ('message',) for err in excinfo.value.errors())


class TestResumeDataInput:
    def test_resume_data_input_valid_all_fields(self):
        data = {
            "skills": ["Python", "FastAPI"],
            "experience": ["Software Engineer for 5 years"],
            "education": ["BSc Computer Science"],
            "location": "Colombo"
        }
        resume_input = ResumeDataInput(**data)
        assert resume_input.skills == data["skills"]
        assert resume_input.experience == data["experience"]
        assert resume_input.education == data["education"]
        assert resume_input.location == data["location"]

    def test_resume_data_input_valid_defaults(self):
        resume_input = ResumeDataInput()
        assert resume_input.skills == []
        assert resume_input.experience == []
        assert resume_input.education == []
        assert resume_input.location is None

    def test_resume_data_input_skills_not_list(self):
        with pytest.raises(ValidationError) as excinfo:
            ResumeDataInput(skills="Python") # type: ignore
        # Pydantic v1 error message style:
        # assert "value is not a valid list" in str(excinfo.value).lower()
        # Pydantic v2 error message style (more specific):
        assert any(err['type'] == 'list_type' and err['loc'] == ('skills',) for err in excinfo.value.errors())


    def test_resume_data_input_location_invalid_type(self):
        with pytest.raises(ValidationError) as excinfo:
            ResumeDataInput(location=123) # type: ignore
        # Pydantic v1:
        # assert "str type expected" in str(excinfo.value).lower() or "none type expected" in str(excinfo.value).lower()
        # Pydantic v2:
        assert any(
            (err['type'] == 'string_type' or err['type'] == 'model_attributes_type') and # model_attributes_type covers None
            err['loc'] == ('location',)
            for err in excinfo.value.errors()
        )

    def test_resume_data_input_extra_field(self):
        # Pydantic models by default ignore extra fields
        data = {
            "skills": ["Python"],
            "extra_field": "should be ignored"
        }
        resume_input = ResumeDataInput(**data)
        assert resume_input.skills == ["Python"]
        assert not hasattr(resume_input, "extra_field")