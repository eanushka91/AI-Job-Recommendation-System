from fastapi.testclient import TestClient
import io


# Mock fixtures would typically be defined in conftest.py or imported
# For this example, assume they are available in the test execution context.

def test_upload_cv_success(
        client: TestClient,
        mock_s3_upload,  # Assuming this mock is set up to return a URL
        mock_user_model_create,  # Assuming this mock is set up
        mock_user_model_get_by_id,  # Assuming this mock is set up
        mock_resume_model_create,  # Assuming this mock is set up
        mock_recommendation_engine_get_recommendations,  # Assuming this mock is set up
):
    # Mock return values for successful operation
    mock_s3_upload.return_value = "http://fake-s3-url.com/test.pdf"
    # Simulate user creation or retrieval
    mock_user_model_create.return_value = {"id": 123, "created": True}  # Example return
    mock_user_model_get_by_id.return_value = {"id": 123}  # Example if user_id is passed and found
    mock_resume_model_create.return_value = {"id": 456}  # Example resume creation
    mock_recommendation_engine_get_recommendations.return_value = [{"job_title": "Test Job"}]

    pdf_content = b"%PDF-1.4\n%test content"
    # Correct way to structure file_data for FastAPI TestClient
    # file_data should be a dictionary for the 'files' parameter
    files = {"file": ("cv.pdf", io.BytesIO(pdf_content), "application/pdf")}
    form_data = {"skills": "s1,s2", "experience": "e1", "education": "d1"}

    response = client.post(
        "/api/upload-cv",
        files=files,
        data=form_data,  # Use 'data' for form fields when 'files' is also present
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}. Response: {response.text}"
    data = response.json()
    assert data["message"] == "CV uploaded successfully!"
    assert data["s3_url"] == "http://fake-s3-url.com/test.pdf"
    assert "user_id" in data
    # assert data["user_created"] is True # This depends on your API logic (new user vs existing)
    assert "resume_id" in data
    assert "recommendations" in data

    mock_s3_upload.assert_called_once()
    mock_resume_model_create.assert_called_once()
    mock_recommendation_engine_get_recommendations.assert_called_once()


def test_upload_cv_invalid_file_type(client: TestClient):
    txt_content = b"not a pdf"
    files = {"file": ("cv.txt", io.BytesIO(txt_content), "text/plain")}
    form_data = {"skills": "a", "experience": "b", "education": "c"}

    response = client.post(
        "/api/upload-cv",
        files=files,
        data=form_data,
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}. Response: {response.text}"

    actual_detail = response.json()["detail"]
    expected_detail = "Only PDF, DOC, DOCX files are allowed. Got: .txt"
    assert actual_detail == expected_detail


def test_upload_cv_s3_failure(
        client: TestClient,
        mock_s3_upload,
):
    s3_error_msg = "Mocked S3 Upload Exception"
    mock_s3_upload.side_effect = Exception(s3_error_msg)

    pdf_content = b"%PDF-1.4\n%s3_fail"
    files = {"file": ("s3_fail.pdf", io.BytesIO(pdf_content), "application/pdf")}
    form_data = {"skills": "s", "experience": "f", "education": "t"}

    response = client.post(
        "/api/upload-cv",
        files=files,
        data=form_data,
    )

    assert response.status_code == 500, f"Expected 500, got {response.status_code}. Response: {response.text}"
    # The original check was:
    # assert ("internal server error occurred during CV upload" in response.json()["detail"])
    # This is a good way to check for partial strings. Let's ensure it's precise if possible,
    # or stick to `in` if the error message might have other dynamic parts.
    # If the error is exactly "Internal server error occurred during CV upload. Reason: Mocked S3 Upload Exception"
    # then an exact match might be too brittle if "Reason" changes.
    # Sticking to `in` for more general internal server errors.
    assert "internal server error occurred during CV upload" in response.json()["detail"]
    # Optionally, you might want to check if the specific S3 error is logged or part of a more detailed internal message
    # but not necessarily exposed directly to the client in this exact way.


def test_upload_cv_user_not_found(
        client: TestClient, mock_s3_upload, mock_user_model_get_by_id
):
    mock_s3_upload.return_value = "http://fake-s3-url.com/user_not_found.pdf"
    user_id_not_found = 404  # This is an ID, not a status code for the mock
    mock_user_model_get_by_id.return_value = None  # Simulate user not found

    pdf_content = b"%PDF-1.4\n%user_not_found"
    files = {"file": ("user_not_found.pdf", io.BytesIO(pdf_content), "application/pdf")}
    form_data = {
        "skills": "a",
        "experience": "b",
        "education": "c",
        "user_id": str(user_id_not_found),  # Pass user_id in form data
    }

    response = client.post(
        "/api/upload-cv",
        files=files,
        data=form_data,
    )

    assert response.status_code == 404, f"Expected 404, got {response.status_code}. Response: {response.text}"
    assert f"User with ID {user_id_not_found} not found" in response.json()["detail"]

