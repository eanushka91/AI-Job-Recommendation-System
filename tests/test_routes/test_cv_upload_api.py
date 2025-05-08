import pytest
from fastapi.testclient import TestClient
from fastapi import UploadFile # TestClient එක්ක UploadFile කෙලින්ම use වෙන්නෙ නෑ, ඒත් type hinting වලට තියෙන්න පුළුවන්
import io # To create a byte stream for the dummy file

# client fixture එක conftest.py එකෙන් එනවා.
# mock fixtures ටිකත් conftest.py එකෙන් එනවා.

def test_upload_cv_success(
    client: TestClient,
    mock_s3_upload,
    mock_user_model_create,
    mock_user_model_get_by_id,
    mock_resume_model_create,
    mock_recommendation_engine_get_recommendations # Mock this as it's called in the endpoint
):
    # Create a dummy PDF file content
    pdf_content = b"%PDF-1.4\n%blah blah blah"
    # When using TestClient, files are passed as a dictionary of tuples:
    # (filename, file-like-object, content_type)
    file_data = ("test_cv.pdf", io.BytesIO(pdf_content), "application/pdf")

    response = client.post(
        "/api/upload-cv",
        files={"file": file_data},
        data={
            "skills": "python, fastapi",
            "experience": "software engineer, 2 years",
            "education": "bsc computer science",
            "location": "Colombo",
            # "user_id": 1 # Optional: Test with pre-existing user if needed
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "CV uploaded and data stored successfully!"
    assert data["url"] == "http://fake-s3-url.com/test.pdf" # From mock_s3_upload
    assert "user_id" in data
    assert "resume_id" in data
    assert "recommendations" in data
    assert "items" in data["recommendations"] # Paginated structure

    mock_s3_upload.assert_called_once()
    # If user_id is not provided, a new user should be created
    mock_user_model_create.assert_called_once()
    # If user_id IS provided, get_by_id would be called, create wouldn't. Adjust assert accordingly.
    # mock_user_model_get_by_id.assert_called_once() # This would be called if user_id was passed
    mock_resume_model_create.assert_called_once()
    mock_recommendation_engine_get_recommendations.assert_called_once()


def test_upload_cv_invalid_file_type(client: TestClient):
    txt_content = b"This is a text file, not a PDF."
    file_data = ("test_cv.txt", io.BytesIO(txt_content), "text/plain")

    response = client.post(
        "/api/upload-cv",
        files={"file": file_data},
        data={
            "skills": "writing",
            "experience": "author",
            "education": "literature"
            # Location will use default
        }
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Only PDF files are allowed"


def test_upload_cv_s3_failure(
    client: TestClient,
    mock_s3_upload, # This mock will be configured to raise an exception
    mock_user_model_create, # These are included to satisfy the fixture requirements of the test
    mock_user_model_get_by_id # but might not be called if S3 fails early.
):
    # Configure the mock_s3_upload to simulate an S3 failure by raising an Exception.
    # The specific message "S3 upload error from mock" is what our mock will raise.
    # The route's general `except Exception as e:` block will catch this.
    s3_exception_message = "S3 upload error from mock"
    mock_s3_upload.side_effect = Exception(s3_exception_message)

    pdf_content = b"%PDF-1.4\n%blah" # Dummy PDF content
    file_data = ("test_cv.pdf", io.BytesIO(pdf_content), "application/pdf")

    response = client.post(
        "/api/upload-cv",
        files={"file": file_data},
        data={
            "skills": "skill_a",
            "experience": "exp_b",
            "education": "edu_c"
            # location will use default, user_id not provided
        }
    )

    assert response.status_code == 500 # Expecting a server error

    # The error message from routes.py's generic exception handler is:
    # f"An error occurred: {str(e)}"
    # where str(e) will be s3_exception_message from our mock.
    expected_response_message = f"An error occurred: {s3_exception_message}"
    assert response.json()["message"] == expected_response_message

    mock_s3_upload.assert_called_once() # Verify that S3 upload was attempted
    # If S3 upload fails, user creation and resume creation should not happen.
    mock_user_model_create.assert_not_called()
    # mock_resume_model_create.assert_not_called() # Add this if mock_resume_model_create is a param


def test_upload_cv_existing_user_not_found(
    client: TestClient,
    mock_s3_upload, # Assume S3 upload is successful for this test case
    mock_user_model_get_by_id # This mock will simulate user not found
):
    # S3 upload is successful
    mock_s3_upload.return_value = "http://fake-s3-url.com/cv.pdf"

    # UserModel.get_by_id will return None, simulating user not found
    mock_user_model_get_by_id.return_value = None
    non_existent_user_id = 999

    pdf_content = b"%PDF-1.4\n%another_cv"
    file_data = ("another_cv.pdf", io.BytesIO(pdf_content), "application/pdf")

    response = client.post(
        "/api/upload-cv",
        files={"file": file_data},
        data={
            "skills": "some_skill",
            "experience": "some_exp",
            "education": "some_edu",
            "user_id": str(non_existent_user_id) # Pass the user_id as a form field (string)
        }
    )

    assert response.status_code == 404 # Not Found
    expected_message = f"User with ID {non_existent_user_id} not found"
    assert response.json()["message"] == expected_message

    mock_s3_upload.assert_called_once() # S3 upload should have been called
    mock_user_model_get_by_id.assert_called_once_with(non_existent_user_id) # Check it was called with the right ID

# You should also add a test case where user_id IS provided AND the user IS found.
def test_upload_cv_with_existing_user_found(
    client: TestClient,
    mock_s3_upload,
    mock_user_model_get_by_id, # Will return a user
    mock_user_model_create,    # Should NOT be called
    mock_resume_model_create,
    mock_recommendation_engine_get_recommendations
):
    existing_user_id = 123
    mock_s3_upload.return_value = "http://fake-s3-url.com/existing_user_cv.pdf"
    # mock_user_model_get_by_id is already configured in conftest to return a user by default
    # but we can be explicit if needed or if the default user_id is different
    mock_user_model_get_by_id.return_value = {"id": existing_user_id, "created_at": "some_date"}

    pdf_content = b"%PDF-1.4\n%user_exists_cv"
    file_data = ("user_exists_cv.pdf", io.BytesIO(pdf_content), "application/pdf")

    response = client.post(
        "/api/upload-cv",
        files={"file": file_data},
        data={
            "skills": "tester",
            "experience": "qa",
            "education": "cert",
            "user_id": str(existing_user_id) # Provide existing user_id
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == existing_user_id
    assert data["user_created"] is False # User was not created, was existing

    mock_s3_upload.assert_called_once()
    mock_user_model_get_by_id.assert_called_once_with(existing_user_id)
    mock_user_model_create.assert_not_called() # IMPORTANT: New user should not be created
    mock_resume_model_create.assert_called_once()
    mock_recommendation_engine_get_recommendations.assert_called_once()