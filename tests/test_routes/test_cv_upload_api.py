# tests/test_routes/test_cv_upload_api.py

# import pytest # Removed F401
from fastapi.testclient import TestClient
# from fastapi import UploadFile # Removed F401 - Not directly used in test logic
import io

# Fixtures like 'client', 'mock_s3_upload', etc., are expected from conftest.py

def test_upload_cv_success(
    client: TestClient,
    mock_s3_upload,
    mock_user_model_create,
    mock_user_model_get_by_id,
    mock_resume_model_create,
    mock_recommendation_engine_get_recommendations # Ensure this mock is in conftest
):
    pdf_content = b"%PDF-1.4\n%test content"
    file_data = ("cv.pdf", io.BytesIO(pdf_content), "application/pdf")

    response = client.post(
        "/api/upload-cv",
        files={"file": file_data},
        data={"skills": "s1,s2", "experience": "e1", "education": "d1"}
    )
    assert response.status_code == 201 # Check for 201 Created
    data = response.json()
    assert data["message"] == "CV uploaded successfully!" # Match updated message
    assert data["s3_url"] == "http://fake-s3-url.com/test.pdf"
    assert "user_id" in data
    assert data["user_created"] is True
    assert "resume_id" in data
    assert "recommendations" in data

    # Verify mocks were called as expected
    mock_s3_upload.assert_called_once()
    mock_user_model_create.assert_called_once()
    mock_resume_model_create.assert_called_once()
    mock_recommendation_engine_get_recommendations.assert_called_once()

def test_upload_cv_invalid_file_type(client: TestClient):
    txt_content = b"not a pdf"
    file_data = ("cv.txt", io.BytesIO(txt_content), "text/plain")

    response = client.post(
        "/api/upload-cv",
        files={"file": file_data},
        data={"skills": "a", "experience": "b", "education": "c"}
    )
    assert response.status_code == 400
    # Check detail field if using HTTPException now
    assert response.json()["detail"] == "Only PDF files are allowed."
    # Or if still using JSONResponse:
    # assert response.json()["message"] == "Only PDF files are allowed."


def test_upload_cv_s3_failure(
    client: TestClient,
    mock_s3_upload,
    mock_user_model_create,
    mock_user_model_get_by_id
):
    s3_error_msg = "Mocked S3 Upload Exception"
    mock_s3_upload.side_effect = Exception(s3_error_msg)

    pdf_content = b"%PDF-1.4\n%s3_fail"
    file_data = ("s3_fail.pdf", io.BytesIO(pdf_content), "application/pdf")

    response = client.post(
        "/api/upload-cv",
        files={"file": file_data},
        data={"skills": "s", "experience": "f", "education": "t"}
    )

    assert response.status_code == 500
    # Check detail field if using HTTPException now
    assert "internal server error occurred during CV upload" in response.json()["detail"]
    # Or if still using JSONResponse:
    # assert f"An error occurred: {s3_error_msg}" in response.json()["message"]


def test_upload_cv_user_not_found(
    client: TestClient,
    mock_s3_upload,
    mock_user_model_get_by_id
):
    mock_s3_upload.return_value = "http://fake-s3-url.com/user_not_found.pdf"
    user_id_not_found = 404
    mock_user_model_get_by_id.return_value = None # Simulate user not found

    pdf_content = b"%PDF-1.4\n%user_not_found"
    file_data = ("user_not_found.pdf", io.BytesIO(pdf_content), "application/pdf")

    response = client.post(
        "/api/upload-cv",
        files={"file": file_data},
        data={"skills": "a", "experience": "b", "education": "c", "user_id": str(user_id_not_found)}
    )

    assert response.status_code == 404
    assert f"User with ID {user_id_not_found} not found" in response.json()["detail"]
    # Or if using JSONResponse:
    # assert response.json()["message"] == f"User with ID {user_id_not_found} not found"

# Add other tests for routes...
